"""Company gallery routes — split from server.py.

Endpoints:
- POST   /api/me/gallery              — add a photo
- GET    /api/users/{user_id}/gallery — public gallery list
- DELETE /api/me/gallery/{photo_id}   — remove a photo (owner only)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException


def register_gallery_routes(api_router, db, get_current_user):
    @api_router.post("/me/gallery")
    async def add_photo(body: dict, user=Depends(get_current_user)):
        if user["role"] != "company":
            raise HTTPException(403, "Entreprises uniquement")
        pid = f"p_{uuid.uuid4().hex[:10]}"
        entry = {
            "photo_id": pid, "user_id": user["user_id"],
            "file_id": body.get("file_id"),
            "url": body.get("url"),
            "title": body.get("title", "Photo"),
            "is_hidden": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.company_photos.insert_one(entry)
        entry.pop("_id", None)
        return entry

    @api_router.get("/users/{user_id}/gallery")
    async def get_gallery(user_id: str):
        return await db.company_photos.find(
            {"user_id": user_id, "is_hidden": {"$ne": True}}, {"_id": 0},
        ).to_list(100)

    @api_router.delete("/me/gallery/{photo_id}")
    async def remove_photo(photo_id: str, user=Depends(get_current_user)):
        await db.company_photos.delete_one(
            {"photo_id": photo_id, "user_id": user["user_id"]},
        )
        return {"ok": True}
