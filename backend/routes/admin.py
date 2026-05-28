"""Admin user-management routes — split from server.py.

Endpoints:
- GET  /api/admin/stats         — counters (users / companies / candidates / offers / applications / posts)
- GET  /api/admin/users         — list of all users (no passwords)
- POST /api/admin/verify/{id}   — manually verify a company account + its offers
- POST /api/admin/grant-premium/{id}?days=30 — grant premium for `days` to any user
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import Depends, HTTPException


def register_admin_routes(api_router, db, get_current_user):
    @api_router.get("/admin/stats")
    async def admin_stats(user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin uniquement")
        return {
            "users": await db.users.count_documents({}),
            "companies": await db.users.count_documents({"role": "company"}),
            "candidates": await db.users.count_documents({"role": "candidate"}),
            "offers": await db.offers.count_documents({}),
            "applications": await db.applications.count_documents({}),
            "posts": await db.posts.count_documents({}),
        }

    @api_router.get("/admin/users")
    async def admin_users(user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin uniquement")
        return await db.users.find({}, {"_id": 0, "password": 0}).to_list(500)

    @api_router.post("/admin/verify/{user_id}")
    async def verify_company(user_id: str, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin uniquement")
        target = await db.users.find_one({"user_id": user_id})
        if not target:
            raise HTTPException(404, "Introuvable")
        p = target.get("profile", {})
        p["verified"] = True
        await db.users.update_one({"user_id": user_id}, {"$set": {"profile": p}})
        await db.offers.update_many({"company_id": user_id}, {"$set": {"verified": True}})
        return {"ok": True}

    @api_router.post("/admin/grant-premium/{user_id}")
    async def grant_premium(user_id: str, days: int = 30, user=Depends(get_current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin")
        target = await db.users.find_one({"user_id": user_id})
        if not target:
            raise HTTPException(404, "Introuvable")
        p = target.get("profile", {})
        now = datetime.now(timezone.utc)
        p["is_premium"] = True
        p["premium_start_date"] = now.isoformat()
        p["premium_end_date"] = (now + timedelta(days=days)).isoformat()
        p["premium_status"] = "active"
        await db.users.update_one({"user_id": user_id}, {"$set": {"profile": p}})
        return {"ok": True, "until": p["premium_end_date"]}
