"""Sponsored advertisements module — Phase H+.

Workflow:
- A company creates an ad → status="pending"
- Free companies are limited to 1 ad max ; companies with active subscription = unlimited
- Any edit on a validated ad pushes it back to "pending"
- Admin validates / refuses / suspends / reactivates / deletes
- Validated ads (within start/end window) are shown in the Bons Plans page with a "Sponsorisé" badge
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

AdStatus = Literal["draft", "pending", "published", "refused", "suspended", "expired"]


class AdBlock(BaseModel):
    """Drag-and-drop builder block (text / image / logo / button / promo_code / link / banner)."""
    id: Optional[str] = None
    type: str  # text|image|logo|button|promo_code|link|banner
    content: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    style: dict = Field(default_factory=dict)
    order: int = 0


class AdStyle(BaseModel):
    bg_color: Optional[str] = "#ffffff"
    text_color: Optional[str] = "#0f172a"
    accent_color: Optional[str] = "#2563eb"
    font_family: Optional[str] = "Inter"
    text_align: Optional[str] = "left"
    border_radius: Optional[int] = 16


class AdIn(BaseModel):
    title: str
    short_text: Optional[str] = ""
    image: Optional[str] = None
    logo: Optional[str] = None
    cta_label: Optional[str] = "Découvrir"
    cta_url: Optional[str] = None
    promo_code: Optional[str] = None
    category: Optional[str] = "general"
    region: Optional[str] = None
    city: Optional[str] = None
    geo_zone: Optional[str] = None  # free text "Île-de-France", "Paris 10°", etc.
    start_date: Optional[str] = None  # ISO date
    end_date: Optional[str] = None
    blocks: List[AdBlock] = Field(default_factory=list)
    style: Optional[AdStyle] = None
    template_id: Optional[str] = None
    save_as_draft: bool = False


def register_ads_routes(api_router, db, get_current_user, notify, company_subscription_active):
    """Mount /ads + /admin/ads endpoints on the provided APIRouter (which must include /api prefix)."""

    # ---------- Company quota helper ----------
    async def _company_quota_ok(company_id: str) -> tuple[bool, int, int]:
        """Return (allowed, current_count, max_allowed). Drafts are NOT counted toward quota."""
        pro = await company_subscription_active(company_id)
        max_allowed = 9999 if pro else 1
        current = await db.ads.count_documents({
            "company_id": company_id,
            "status": {"$in": ["pending", "published", "suspended"]},
        })
        return (current < max_allowed, current, max_allowed)

    # ---------- COMPANY CRUD ----------
    @api_router.post("/ads")
    async def create_ad(data: AdIn, user=Depends(get_current_user)):
        if user["role"] != "company":
            raise HTTPException(403, "Réservé aux entreprises")
        allowed, current, max_a = await _company_quota_ok(user["user_id"])
        if not allowed and not data.save_as_draft:
            raise HTTPException(
                402,
                f"Quota atteint ({current}/{max_a}). Passez à l'offre Pro pour publier davantage de publicités."
            )
        ad_id = f"ad_{uuid.uuid4().hex[:12]}"
        status = "draft" if data.save_as_draft else "pending"
        doc = {
            "ad_id": ad_id,
            "company_id": user["user_id"],
            "company_name": user.get("name"),
            "company_logo": (user.get("profile") or {}).get("logo")
                            or (user.get("profile") or {}).get("avatar"),
            **data.model_dump(),
            "status": status,
            "views": 0,
            "clicks": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.ads.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @api_router.get("/ads/mine")
    async def my_ads(user=Depends(get_current_user)):
        if user["role"] != "company":
            raise HTTPException(403, "Réservé aux entreprises")
        ads = await db.ads.find({"company_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
        pro = await company_subscription_active(user["user_id"])
        active = [a for a in ads if a["status"] in ("pending", "published", "suspended")]
        return {
            "ads": ads,
            "quota": {"max": (9999 if pro else 1), "used": len(active)},
            "pro": pro,
        }

    @api_router.get("/ads/public")
    async def list_public_ads(category: Optional[str] = None,
                              region: Optional[str] = None,
                              city: Optional[str] = None,
                              limit: int = 30):
        """Public list — only validated ads within their start/end window."""
        now_iso = datetime.now(timezone.utc).isoformat()
        query: dict = {"status": "published"}
        # window: start_date <= now <= end_date when set
        date_clauses = []
        date_clauses.append({"$or": [{"start_date": None}, {"start_date": {"$lte": now_iso}}]})
        date_clauses.append({"$or": [{"end_date": None}, {"end_date": {"$gte": now_iso}}]})
        query["$and"] = date_clauses
        if category and category != "all":
            query["category"] = category
        if region:
            query["region"] = region
        if city:
            query["city"] = {"$regex": city, "$options": "i"}
        ads = await db.ads.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 100))
        return ads

    @api_router.get("/ads/{ad_id}")
    async def get_ad(ad_id: str):
        ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
        if not ad:
            raise HTTPException(404, "Publicité introuvable")
        return ad

    @api_router.patch("/ads/{ad_id}")
    async def update_ad(ad_id: str, data: dict, user=Depends(get_current_user)):
        ad = await db.ads.find_one({"ad_id": ad_id})
        if not ad:
            raise HTTPException(404, "Introuvable")
        is_admin = user["role"] == "admin"
        if ad["company_id"] != user["user_id"] and not is_admin:
            raise HTTPException(403, "Interdit")
        allowed = {"title", "short_text", "image", "logo", "cta_label", "cta_url",
                   "promo_code", "category", "region", "city", "geo_zone",
                   "start_date", "end_date", "blocks", "style", "template_id"}
        upd = {k: v for k, v in data.items() if k in allowed}
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Author edits a validated/refused/suspended ad => back to pending
        if not is_admin and ad.get("status") in ("published", "suspended", "refused"):
            upd["status"] = "pending"
        # Author can also submit a draft for validation
        if not is_admin and ad.get("status") == "draft" and data.get("submit"):
            # Re-check quota when promoting a draft to pending
            allowed, current, max_a = await _company_quota_ok(user["user_id"])
            if not allowed:
                raise HTTPException(
                    402,
                    f"Quota atteint ({current}/{max_a}). Passez à l'offre Pro pour publier davantage de publicités."
                )
            upd["status"] = "pending"
        await db.ads.update_one({"ad_id": ad_id}, {"$set": upd})
        return {"ok": True, "status": upd.get("status", ad.get("status"))}

    @api_router.delete("/ads/{ad_id}")
    async def delete_ad(ad_id: str, user=Depends(get_current_user)):
        ad = await db.ads.find_one({"ad_id": ad_id})
        if not ad:
            raise HTTPException(404, "Introuvable")
        if ad["company_id"] != user["user_id"] and user["role"] != "admin":
            raise HTTPException(403, "Interdit")
        await db.ads.delete_one({"ad_id": ad_id})
        return {"ok": True}

    # ---------- TRACKING ----------
    async def _dedup_track(ad_id: str, action: str, ip: str) -> bool:
        """Return True if this (ad_id, action, ip) hasn't been counted in the last hour.
        Relies on a TTL index on ad_tracking_dedup.expires_at to clean up entries automatically."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        key = f"{ad_id}:{action}:{ip}"
        try:
            await db.ad_tracking_dedup.insert_one({
                "_id": key,
                "ad_id": ad_id,
                "action": action,
                "ip": ip,
                "expires_at": now + timedelta(hours=1),
                "created_at": now,
            })
            return True
        except Exception:
            return False

    @api_router.post("/ads/{ad_id}/view")
    async def track_view(ad_id: str, request: Request):
        ip = request.client.host if request.client else "unknown"
        if await _dedup_track(ad_id, "view", ip):
            await db.ads.update_one({"ad_id": ad_id}, {"$inc": {"views": 1}})
        # TTL index on ad_tracking_dedup.expires_at handles cleanup automatically
        return {"ok": True}

    @api_router.post("/ads/{ad_id}/click")
    async def track_click(ad_id: str, request: Request):
        ip = request.client.host if request.client else "unknown"
        if await _dedup_track(ad_id, "click", ip):
            await db.ads.update_one({"ad_id": ad_id}, {"$inc": {"clicks": 1}})
        return {"ok": True}

    # ---------- ADMIN ----------
    @api_router.get("/admin/ads")
    async def admin_list_ads(status: Optional[str] = None,
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
                {"short_text": {"$regex": q, "$options": "i"}},
                {"company_name": {"$regex": q, "$options": "i"}},
            ]
        ads = await db.ads.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
        counts: dict = {}
        for s in ("draft", "pending", "published", "refused", "suspended", "expired"):
            counts[s] = await db.ads.count_documents({"status": s})
        counts["all"] = await db.ads.count_documents({})

        # Aggregate stats
        agg = await db.ads.aggregate([
            {"$group": {
                "_id": None,
                "total_views": {"$sum": "$views"},
                "total_clicks": {"$sum": "$clicks"},
                "ads": {"$sum": 1},
            }},
        ]).to_list(1)
        stats_doc = agg[0] if agg else {"total_views": 0, "total_clicks": 0, "ads": 0}
        # Cap CTR at 100% — clicks can exceed views from non-deduped tracking, but UX-wise CTR > 100% is misleading
        ctr = min(stats_doc["total_clicks"] / stats_doc["total_views"] * 100, 100.0) if stats_doc.get("total_views") else 0.0
        stats_doc["ctr"] = round(ctr, 2)
        stats_doc.pop("_id", None)

        return {"ads": ads, "counts": counts, "stats": stats_doc}

    @api_router.post("/admin/ads/{ad_id}/validate")
    async def admin_validate_ad(ad_id: str, body: dict, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        action = body.get("action")
        ad = await db.ads.find_one({"ad_id": ad_id})
        if not ad:
            raise HTTPException(404, "Introuvable")
        new_status = {
            "approve": "published",
            "validate": "published",
            "refuse": "refused",
            "suspend": "suspended",
            "reactivate": "published",
            "expire": "expired",
        }.get(action)
        if not new_status:
            raise HTTPException(400, "Action invalide")
        reason = (body.get("reason") or "").strip()
        set_doc = {
            "status": new_status,
            "moderated_by": user["user_id"],
            "moderated_at": datetime.now(timezone.utc).isoformat(),
        }
        if reason:
            set_doc["moderation_reason"] = reason
        await db.ads.update_one({"ad_id": ad_id}, {"$set": set_doc})
        msg = {
            "published": f"Votre publicité \"{ad['title']}\" est validée et diffusée ✓",
            "refused": f"Votre publicité \"{ad['title']}\" a été refusée" + (f" — {reason}" if reason else ""),
            "suspended": f"Votre publicité \"{ad['title']}\" a été suspendue" + (f" — {reason}" if reason else ""),
            "expired": f"Votre publicité \"{ad['title']}\" est expirée",
        }
        await notify(ad["company_id"], "ad_validation",
                     msg.get(new_status, f"Publicité: {new_status}"),
                     f"/ads/{ad_id}")
        return {"ok": True, "status": new_status}
