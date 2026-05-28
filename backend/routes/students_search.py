"""Search students by company / by admin — split from server.py.

Endpoints:
- GET /api/search/students         — filter by name + level + domain + city + skill + status
- GET /api/search/students-nearby  — geo-radius search (company / admin only)
"""
from __future__ import annotations

import re as _re
from typing import Optional

from fastapi import Depends, HTTPException


def register_students_search_routes(api_router, db, get_current_user, get_coords_async, haversine, get_coords):
    @api_router.get("/search/students")
    async def search_students(
        q: Optional[str] = None,
        level: Optional[str] = None,
        domain: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        contract_type: Optional[str] = None,
        student_status: Optional[str] = None,
        skill: Optional[str] = None,
        limit: int = 50,
        user=Depends(get_current_user),
    ):
        if user["role"] not in ("company", "admin"):
            raise HTTPException(403, "Réservé aux entreprises")
        query: dict = {"role": "candidate"}
        if q:
            rx = {"$regex": _re.escape(q), "$options": "i"}
            query["$or"] = [
                {"name": rx},
                {"profile.first_name": rx},
                {"profile.last_name": rx},
            ]
        if level: query["profile.level"] = level
        if domain: query["profile.domain"] = {"$regex": domain, "$options": "i"}
        if city: query["profile.city"] = {"$regex": city, "$options": "i"}
        if region: query["profile.region"] = region
        if contract_type: query["profile.contract_type"] = contract_type
        if student_status: query["profile.status"] = student_status
        if skill: query["profile.skills"] = {"$regex": skill, "$options": "i"}
        users = await db.users.find(query, {"_id": 0, "password": 0}).limit(limit).to_list(limit)
        return users

    @api_router.get("/search/students-nearby")
    async def students_nearby(city: str, distance_km: float = 50, limit: int = 100,
                              user=Depends(get_current_user)):
        if user["role"] not in ("company", "admin"):
            raise HTTPException(403, "Réservé aux entreprises")
        coords = await get_coords_async(city)
        if not coords:
            raise HTTPException(404, f"Ville introuvable: {city}. Vérifiez l'orthographe.")
        lat0, lon0 = coords
        students = await db.users.find(
            {"role": "candidate"}, {"_id": 0, "password": 0},
        ).to_list(2000)
        result = []
        for s in students:
            sc = get_coords(s.get("profile", {}).get("city"))
            if not sc:
                continue
            d = haversine(lat0, lon0, sc[0], sc[1])
            if d <= distance_km:
                s["distance_km"] = round(d, 1)
                result.append(s)
        result.sort(key=lambda x: x["distance_km"])
        return result[:limit]
