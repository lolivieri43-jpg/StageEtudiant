"""Reports / Moderation routes — Phase Moderation (signalements posts/comments).

Workflow:
- Any authenticated user can report a post or a comment with a reason
- Status: pending → reviewed (kept | removed)
- Admin queue: GET /api/admin/reports?status=...
- Admin action: dismiss (keep content) or remove (delete the target + notify author)
- A user cannot report the same target twice
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel


REASONS = [
    "spam", "harassment", "hate_speech", "violence",
    "inappropriate", "misinformation", "scam", "other",
]


class ReportIn(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: str
    reason: str
    details: Optional[str] = None


def register_moderation_routes(api_router, db, get_current_user, notify):
    async def _find_target(target_type: str, target_id: str):
        if target_type == "post":
            return await db.posts.find_one({"post_id": target_id}, {"_id": 0})
        if target_type == "comment":
            return await db.comments.find_one({"comment_id": target_id}, {"_id": 0})
        return None

    # ---------- USER ENDPOINTS ----------
    @api_router.post("/reports")
    async def create_report(data: ReportIn, user=Depends(get_current_user)):
        reason = (data.reason or "").strip().lower()
        if reason not in REASONS:
            raise HTTPException(400, f"Raison invalide. Choisir parmi : {', '.join(REASONS)}")
        target = await _find_target(data.target_type, data.target_id)
        if not target:
            raise HTTPException(404, "Élément introuvable")
        if target.get("author_id") == user["user_id"]:
            raise HTTPException(400, "Vous ne pouvez pas signaler votre propre contenu")
        existing = await db.reports.find_one({
            "target_type": data.target_type,
            "target_id": data.target_id,
            "reporter_id": user["user_id"],
        })
        if existing:
            raise HTTPException(400, "Vous avez déjà signalé ce contenu")
        report_id = f"rep_{uuid.uuid4().hex[:12]}"
        await db.reports.insert_one({
            "report_id": report_id,
            "target_type": data.target_type,
            "target_id": data.target_id,
            "target_author_id": target.get("author_id"),
            "target_excerpt": (target.get("content") or "")[:200],
            "reason": reason,
            "details": (data.details or "")[:500] or None,
            "reporter_id": user["user_id"],
            "reporter_name": user["name"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "report_id": report_id}

    @api_router.get("/reports/mine")
    async def my_reports(user=Depends(get_current_user)):
        return await db.reports.find(
            {"reporter_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)

    # ---------- ADMIN ENDPOINTS ----------
    @api_router.get("/admin/reports")
    async def admin_list_reports(status: Optional[str] = "pending",
                                 target_type: Optional[str] = None,
                                 limit: int = 200,
                                 user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        query: dict = {}
        if status and status != "all":
            query["status"] = status
        if target_type:
            query["target_type"] = target_type
        reports = await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
        # Enrich reports with current target snapshot
        for r in reports:
            target = await _find_target(r["target_type"], r["target_id"])
            r["target_exists"] = target is not None
            if target:
                r["target_snapshot"] = {
                    "content": target.get("content"),
                    "author_name": target.get("author_name"),
                    "author_id": target.get("author_id"),
                    "created_at": target.get("created_at"),
                    "media": target.get("media") if r["target_type"] == "post" else None,
                }
        counts: dict = {}
        for s in ("pending", "kept", "removed"):
            counts[s] = await db.reports.count_documents({"status": s})
        counts["all"] = await db.reports.count_documents({})
        return {"reports": reports, "counts": counts}

    @api_router.post("/admin/reports/{report_id}/dismiss")
    async def admin_dismiss(report_id: str, body: dict, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        r = await db.reports.find_one({"report_id": report_id})
        if not r:
            raise HTTPException(404, "Signalement introuvable")
        note = (body.get("note") or "").strip()
        await db.reports.update_many(
            {"target_type": r["target_type"], "target_id": r["target_id"]},
            {"$set": {
                "status": "kept",
                "moderated_by": user["user_id"],
                "moderated_at": datetime.now(timezone.utc).isoformat(),
                "moderation_note": note or None,
            }},
        )
        return {"ok": True, "status": "kept"}

    @api_router.post("/admin/reports/{report_id}/remove")
    async def admin_remove(report_id: str, body: dict, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        r = await db.reports.find_one({"report_id": report_id})
        if not r:
            raise HTTPException(404, "Signalement introuvable")
        reason = (body.get("reason") or "").strip()
        target_type = r["target_type"]
        target_id = r["target_id"]
        # Delete the offending content
        if target_type == "post":
            await db.posts.delete_one({"post_id": target_id})
            await db.comments.delete_many({"post_id": target_id})
        elif target_type == "comment":
            comment = await db.comments.find_one({"comment_id": target_id})
            await db.comments.delete_one({"comment_id": target_id})
            if comment:
                await db.posts.update_one(
                    {"post_id": comment["post_id"]},
                    {"$inc": {"comments_count": -1}},
                )
        # Update all reports about this target
        await db.reports.update_many(
            {"target_type": target_type, "target_id": target_id},
            {"$set": {
                "status": "removed",
                "moderated_by": user["user_id"],
                "moderated_at": datetime.now(timezone.utc).isoformat(),
                "moderation_reason": reason or None,
            }},
        )
        # Notify the author
        if r.get("target_author_id"):
            label = "publication" if target_type == "post" else "commentaire"
            msg = f"Votre {label} a été supprimé par la modération"
            if reason:
                msg += f" : {reason}"
            await notify(r["target_author_id"], "moderation_removed", msg, "/feed")
        return {"ok": True, "status": "removed"}

    @api_router.delete("/admin/reports/{report_id}")
    async def admin_delete_report(report_id: str, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        await db.reports.delete_one({"report_id": report_id})
        return {"ok": True}
