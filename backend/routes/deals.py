"""Deals routes — split from server.py.
Workflow: every deal starts as 'pending' (admin moderation), even from companies.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException

from models import DealIn


def register_deals_routes(api_router, db, get_current_user, notify):
    @api_router.post("/deals")
    async def create_deal(data: DealIn, user=Depends(get_current_user)):
        deal_id = f"deal_{uuid.uuid4().hex[:12]}"
        doc = {
            "deal_id": deal_id,
            "author_id": user["user_id"],
            "author_name": user["name"],
            "author_type": user["role"],
            "author_avatar": user.get("profile", {}).get("avatar") or user.get("profile", {}).get("logo"),
            **data.model_dump(),
            "status": "pending",  # all deals validated by admin
            "boosted_until": None,
            "sponsored_until": None,
            "views": 0,
            "clicks": 0,
            "saves": [],
            "shares": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.deals.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @api_router.get("/deals")
    async def list_deals(
        q: Optional[str] = None,
        category: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        author_type: Optional[str] = None,
        status: Optional[str] = "published",
        limit: int = 60,
    ):
        query: dict = {}
        if status:
            query["status"] = status
        if q:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
            ]
        if category:
            query["category"] = category
        if region:
            query["region"] = region
        if city:
            query["city"] = {"$regex": city, "$options": "i"}
        if author_type:
            query["author_type"] = author_type
        deals = await db.deals.find(query, {"_id": 0}).to_list(limit)
        now = datetime.now(timezone.utc)

        def tier(d):
            s = d.get("sponsored_until")
            b = d.get("boosted_until")
            if s and datetime.fromisoformat(s).replace(tzinfo=timezone.utc) > now:
                return 0
            if b and datetime.fromisoformat(b).replace(tzinfo=timezone.utc) > now:
                return 1
            return 2

        deals.sort(key=lambda d: (tier(d), -datetime.fromisoformat(d["created_at"]).timestamp()))
        return deals

    @api_router.get("/deals/mine")
    async def my_deals(user=Depends(get_current_user)):
        deals = await db.deals.find(
            {"author_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        saved_ids = []
        for d in await db.deals.find(
            {"saves": user["user_id"]}, {"_id": 0, "deal_id": 1}
        ).to_list(200):
            saved_ids.append(d["deal_id"])
        saved = await db.deals.find({"deal_id": {"$in": saved_ids}}, {"_id": 0}).to_list(200)
        boosts = await db.boost_orders.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return {"deals": deals, "saved": saved, "boosts": boosts}

    @api_router.get("/deals/{deal_id}")
    async def get_deal(deal_id: str):
        d = await db.deals.find_one({"deal_id": deal_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Bon plan introuvable")
        await db.deals.update_one({"deal_id": deal_id}, {"$inc": {"views": 1}})
        d["views"] = d.get("views", 0) + 1
        return d

    @api_router.patch("/deals/{deal_id}")
    async def update_deal(deal_id: str, data: dict, user=Depends(get_current_user)):
        d = await db.deals.find_one({"deal_id": deal_id})
        if not d:
            raise HTTPException(404, "Introuvable")
        is_admin = user["role"] == "admin"
        if d["author_id"] != user["user_id"] and not is_admin:
            raise HTTPException(403, "Interdit")
        allowed = {"title", "description", "category", "city", "region", "image",
                   "promo_code", "discount", "url", "expires_at"}
        upd = {k: v for k, v in data.items() if k in allowed}
        # Author edits a validated/suspended/refused deal => re-validation
        if upd and not is_admin and d.get("status") in ("published", "suspended", "refused"):
            upd["status"] = "pending"
        if upd:
            await db.deals.update_one({"deal_id": deal_id}, {"$set": upd})
        return {"ok": True, "status": upd.get("status", d.get("status"))}

    @api_router.delete("/deals/{deal_id}")
    async def delete_deal(deal_id: str, user=Depends(get_current_user)):
        d = await db.deals.find_one({"deal_id": deal_id})
        if not d:
            raise HTTPException(404, "Introuvable")
        if d["author_id"] != user["user_id"] and user["role"] != "admin":
            raise HTTPException(403, "Interdit")
        await db.deals.delete_one({"deal_id": deal_id})
        return {"ok": True}

    @api_router.post("/deals/{deal_id}/save")
    async def save_deal(deal_id: str, user=Depends(get_current_user)):
        d = await db.deals.find_one({"deal_id": deal_id})
        if not d:
            raise HTTPException(404, "Introuvable")
        saves = d.get("saves", [])
        if user["user_id"] in saves:
            saves.remove(user["user_id"])
        else:
            saves.append(user["user_id"])
            if d["author_id"] != user["user_id"]:
                await notify(d["author_id"], "deal_save",
                             f"{user['name']} a sauvegardé votre bon plan \"{d['title']}\"",
                             f"/deals/{deal_id}")
        await db.deals.update_one({"deal_id": deal_id}, {"$set": {"saves": saves}})
        return {"saves": saves}

    @api_router.post("/deals/{deal_id}/click")
    async def click_deal(deal_id: str):
        await db.deals.update_one({"deal_id": deal_id}, {"$inc": {"clicks": 1}})
        return {"ok": True}

    @api_router.post("/deals/{deal_id}/share")
    async def share_deal(deal_id: str):
        await db.deals.update_one({"deal_id": deal_id}, {"$inc": {"shares": 1}})
        return {"ok": True}

    # ---------- ADMIN MODERATION ----------
    @api_router.post("/admin/deals/{deal_id}/validate")
    async def validate_deal(deal_id: str, body: dict, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        action = body.get("action")
        deal = await db.deals.find_one({"deal_id": deal_id})
        if not deal:
            raise HTTPException(404, "Introuvable")
        new_status = {
            "approve": "published",
            "validate": "published",
            "refuse": "refused",
            "suspend": "suspended",
            "reactivate": "published",
            "disable": "expired",
            "expire": "expired",
        }.get(action)
        if not new_status:
            raise HTTPException(400, "Action invalide")
        set_doc = {
            "status": new_status,
            "moderated_by": user["user_id"],
            "moderated_at": datetime.now(timezone.utc).isoformat(),
        }
        reason = (body.get("reason") or "").strip()
        if reason:
            set_doc["moderation_reason"] = reason
        await db.deals.update_one({"deal_id": deal_id}, {"$set": set_doc})
        msg_map = {
            "published": f"Votre bon plan \"{deal['title']}\" a été validé ✓",
            "refused": f"Votre bon plan \"{deal['title']}\" a été refusé" + (f" — {reason}" if reason else ""),
            "suspended": f"Votre bon plan \"{deal['title']}\" a été suspendu" + (f" — {reason}" if reason else ""),
            "expired": f"Votre bon plan \"{deal['title']}\" a expiré",
        }
        await notify(deal["author_id"], "deal_validation",
                     msg_map.get(new_status, f"Statut: {new_status}"),
                     f"/deals/{deal_id}")
        return {"ok": True, "status": new_status}

    @api_router.get("/admin/deals")
    async def admin_list_deals(status: Optional[str] = None,
                               q: Optional[str] = None,
                               limit: int = 200,
                               user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        query: dict = {}
        if status and status != "all":
            query["status"] = status
        if q:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"author_name": {"$regex": q, "$options": "i"}},
            ]
        deals = await db.deals.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
        counts: dict = {}
        for s in ("draft", "pending", "published", "refused", "suspended", "expired"):
            counts[s] = await db.deals.count_documents({"status": s})
        counts["all"] = await db.deals.count_documents({})
        return {"deals": deals, "counts": counts}

    @api_router.get("/admin/deals/pending")
    async def admin_pending_deals(user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        return await db.deals.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
