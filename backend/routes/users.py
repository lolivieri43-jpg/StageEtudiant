"""User-profile routes — split from server.py.

Endpoints:
- PUT  /api/profile          — update profile fields
- GET  /api/users/{user_id}  — public profile (logs a profile view, deduped 30 min)
- GET  /api/users            — list users (optional role filter)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException


logger = logging.getLogger(__name__)


def register_users_routes(api_router, db, get_current_user, get_optional_user):
    @api_router.put("/profile")
    async def update_profile(data: dict, user=Depends(get_current_user)):
        profile = user.get("profile", {})
        profile.update({k: v for k, v in data.items() if v is not None})
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"profile": profile}})
        updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password": 0})
        return updated

    @api_router.get("/users/{user_id}")
    async def get_user_public(user_id: str, viewer=Depends(get_optional_user)):
        u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password": 0})
        if not u:
            raise HTTPException(404, "Utilisateur introuvable")
        if viewer and viewer["user_id"] != user_id:
            try:
                cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
                recent = await db.profile_views.find_one({
                    "viewer_user_id": viewer["user_id"],
                    "viewed_user_id": user_id,
                    "viewed_at": {"$gte": cutoff},
                })
                if not recent:
                    await db.profile_views.insert_one({
                        "view_id": f"pv_{uuid.uuid4().hex[:12]}",
                        "viewer_user_id": viewer["user_id"],
                        "viewer_name": viewer.get("name"),
                        "viewer_avatar": viewer.get("profile", {}).get("avatar")
                                        or viewer.get("profile", {}).get("logo"),
                        "viewer_role": viewer.get("role"),
                        "viewed_user_id": user_id,
                        "viewed_role": u.get("role"),
                        "viewed_at": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as e:
                logger.warning(f"profile_view log failed: {e}")
        return u

    @api_router.get("/users")
    async def list_users(role: Optional[str] = None, limit: int = 20):
        q: dict = {}
        if role:
            q["role"] = role
        users = await db.users.find(q, {"_id": 0, "password": 0}).limit(limit).to_list(limit)
        return users
