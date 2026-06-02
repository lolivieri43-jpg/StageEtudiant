"""Offers routes — split from server.py.

Endpoints:
- POST   /api/offers            — company creates an offer
- GET    /api/offers            — search/list offers with full filters (q, region, city,
                                  radius_km, contract_type, domain, level, remote,
                                  company, company_id, source, country, european_only)
- GET    /api/offers/regions    — aggregated stats per region
- GET    /api/offers/{id}       — get a single offer + increment views
- DELETE /api/offers/{id}       — delete (owner or admin)

Premium enrichment: offers from premium companies get company_is_premium=true and bubble
up in the result list (stable sort, premium-first).
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel


class OfferIn(BaseModel):
    title: str
    contract_type: Literal["stage", "alternance"]
    domain: str
    city: str
    region: str
    remote: bool = False
    duration: str
    rhythm: Optional[str] = None
    start_date: Optional[str] = None
    level: str
    skills: list[str] = []
    description: str
    profile: Optional[str] = None
    benefits: Optional[str] = None
    salary: Optional[str] = None


def register_offers_routes(api_router, db, get_current_user, premium_active_from_doc):
    """Attach the offers endpoints to `api_router`.

    `premium_active_from_doc` is passed in so this module doesn't depend on server.py.
    """

    async def _enrich_offers_with_premium(offers: list) -> None:
        if not offers:
            return
        ids = {o.get("company_id") for o in offers if o.get("company_id")}
        if not ids:
            return
        cursor = db.users.find(
            {"user_id": {"$in": list(ids)}, "role": "company"},
            {"_id": 0, "user_id": 1,
             "profile.is_premium": 1, "profile.premium_status": 1, "profile.premium_end_date": 1},
        )
        premium_by_id: dict = {}
        async for u in cursor:
            p = u.get("profile", {}) or {}
            premium_by_id[u["user_id"]] = {
                "is_premium": bool(p.get("is_premium")),
                "premium_status": p.get("premium_status"),
                "premium_end_date": p.get("premium_end_date"),
                "active": premium_active_from_doc({
                    "is_premium": p.get("is_premium"),
                    "premium_status": p.get("premium_status"),
                    "premium_end_date": p.get("premium_end_date"),
                }),
            }
        for o in offers:
            info = premium_by_id.get(o.get("company_id"))
            if not info:
                continue
            o["company_is_premium"] = bool(info["active"])
            o["company_premium_status"] = info["premium_status"]
            o["company_premium_end_date"] = info["premium_end_date"]

    # Expose so legacy callers (e.g. /offers-nearby still in server.py) can import it
    register_offers_routes.enrich = _enrich_offers_with_premium  # type: ignore[attr-defined]

    @api_router.post("/offers")
    async def create_offer(data: OfferIn, user=Depends(get_current_user)):
        if user["role"] != "company":
            raise HTTPException(403, "Réservé aux entreprises")
        offer_id = f"off_{uuid.uuid4().hex[:12]}"
        doc = {
            "offer_id": offer_id,
            "company_id": user["user_id"],
            "company_name": user.get("profile", {}).get("company_name") or user["name"],
            "company_logo": user.get("profile", {}).get("logo"),
            "verified": user.get("profile", {}).get("verified", False),
            **data.model_dump(),
            "views": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.offers.insert_one(doc)
        # Best-effort geocoding so the offer appears on the world map immediately.
        try:
            from routes.map import ensure_offer_coords as _eoc
            await _eoc(db, doc)
        except Exception:
            pass
        doc.pop("_id", None)
        return doc

    @api_router.get("/offers")
    async def list_offers(
        q: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        radius_km: Optional[float] = None,
        contract_type: Optional[str] = None,
        domain: Optional[str] = None,
        level: Optional[str] = None,
        remote: Optional[bool] = None,
        company: Optional[str] = None,
        company_id: Optional[str] = None,
        source: Optional[str] = None,
        country: Optional[str] = None,
        european_only: bool = False,
        limit: int = 200,
    ):
        from geo_search import (
            normalize_text, companies_match, company_contains_term,
            haversine_km, geocode_french_city, offer_coords,
            is_french, is_european, countries_match,
        )
        query: dict = {"is_demo": {"$ne": True}}
        if q:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"domain": {"$regex": q, "$options": "i"}},
                {"company_name": {"$regex": q, "$options": "i"}},
            ]
        if region: query["region"] = region
        if contract_type: query["contract_type"] = contract_type
        if domain: query["domain"] = {"$regex": domain, "$options": "i"}
        if level: query["level"] = level
        if remote is not None: query["remote"] = remote
        if company_id: query["company_id"] = company_id
        if source: query["source"] = source

        fetch_limit = min(max(limit, 200), 1000) * 2
        offers = await db.offers.find(query, {"_id": 0}).sort(
            [("source_priority", -1), ("created_at", -1)]
        ).limit(fetch_limit).to_list(fetch_limit)

        if european_only or (country and normalize_text(country) == "europe"):
            offers = [o for o in offers if is_european(o.get("country")) and not is_french(o.get("country"))]
        elif country:
            offers = [o for o in offers if countries_match(country, o.get("country") or "France")]
        else:
            offers = [o for o in offers if is_french(o.get("country"))]

        if company:
            offers = [o for o in offers
                      if companies_match(o.get("company_name"), company)
                      or company_contains_term(o.get("company_name"), company)]

        if city and not radius_km:
            ncity = normalize_text(city)
            offers = [o for o in offers if ncity in normalize_text(o.get("city"))]

        if radius_km and radius_km > 0:
            from geo_search import geocode_nominatim as _geocode_nominatim
            center = geocode_french_city(city)
            if not center:
                fallback = await _geocode_nominatim(db, city or "")
                if fallback:
                    center = (fallback[0], fallback[1])
            if not center:
                raise HTTPException(400, "Ville introuvable, vérifiez l'orthographe ou élargissez la recherche.")
            clat, clon = center
            kept = []
            for o in offers:
                coords = offer_coords(o)
                if not coords:
                    continue
                d = haversine_km(clat, clon, coords[0], coords[1])
                if d <= radius_km:
                    o["_distance_km"] = round(d, 1)
                    kept.append(o)
            offers = sorted(kept, key=lambda x: x.get("_distance_km", 9999))

        offers = offers[: min(limit, 500)]
        await _enrich_offers_with_premium(offers)
        offers.sort(key=lambda o: 0 if o.get("company_is_premium") else 1)
        return offers

    @api_router.get("/offers/regions")
    async def offers_by_region():
        offers = await db.offers.find({}, {"_id": 0, "region": 1, "company_id": 1}).to_list(1000)
        region_offers = Counter(o["region"] for o in offers if o.get("region"))
        region_companies: dict = {}
        for o in offers:
            r = o.get("region")
            if r:
                region_companies.setdefault(r, set()).add(o["company_id"])
        return {
            "by_region": [
                {"region": r, "offers": region_offers[r], "companies": len(region_companies.get(r, set()))}
                for r in region_offers
            ]
        }

    @api_router.get("/offers/{offer_id}")
    async def get_offer(offer_id: str):
        offer = await db.offers.find_one({"offer_id": offer_id}, {"_id": 0})
        if not offer:
            raise HTTPException(404, "Offre introuvable")
        await db.offers.update_one({"offer_id": offer_id}, {"$inc": {"views": 1}})
        offer["views"] = offer.get("views", 0) + 1
        return offer

    @api_router.delete("/offers/{offer_id}")
    async def delete_offer(offer_id: str, user=Depends(get_current_user)):
        offer = await db.offers.find_one({"offer_id": offer_id})
        if not offer:
            raise HTTPException(404, "Introuvable")
        if offer["company_id"] != user["user_id"] and user["role"] != "admin":
            raise HTTPException(403, "Interdit")
        await db.offers.delete_one({"offer_id": offer_id})
        return {"ok": True}
