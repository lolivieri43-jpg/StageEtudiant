"""Notifications routes — split from server.py."""
from __future__ import annotations

from fastapi import Depends


def register_notifications_routes(api_router, db, get_current_user):
    @api_router.get("/notifications")
    async def list_notifs(user=Depends(get_current_user)):
        n = await db.notifications.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        unread = sum(1 for x in n if not x.get("read"))
        return {"notifications": n, "unread": unread}

    @api_router.post("/notifications/read")
    async def mark_read(user=Depends(get_current_user)):
        await db.notifications.update_many(
            {"user_id": user["user_id"]}, {"$set": {"read": True}}
        )
        return {"ok": True}
