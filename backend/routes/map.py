"""Map / geocoded offers routes — split from server.py.

Endpoints:
- GET /api/offers/map  — returns offers with valid (lat, lon) only; supports filters
                          country, city, contract_type, domain, q (text search).
- POST /api/admin/offers/geocode-backfill — admin-only: iterate offers without coords,
                          call Geoapify (rate-limited), persist results.

Helper:
- ensure_offer_coords(db, offer_doc) — geocode an offer (uses geoapify → fallback nominatim)
                          and persists the `location` and top-level lat/lon fields.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import Depends, HTTPException

from geo_search import (
    geocode_geoapify, geocode_nominatim, geocode_french_city, normalize_text,
)

logger = logging.getLogger(__name__)


def _existing_coords(offer: dict):
    loc = offer.get("location") or {}
    lat = loc.get("latitude") if loc else None
    lon = loc.get("longitude") if loc else None
    if (lat is None or lon is None) and offer.get("coords"):
        c = offer["coords"]
        lat = c.get("lat") if isinstance(c, dict) else None
        lon = c.get("lon") if isinstance(c, dict) else None
    if lat is None and offer.get("latitude") is not None:
        lat = offer["latitude"]
    if lon is None and offer.get("longitude") is not None:
        lon = offer["longitude"]
    try:
        return (float(lat), float(lon)) if (lat is not None and lon is not None) else None
    except (TypeError, ValueError):
        return None


async def ensure_offer_coords(db, offer: dict) -> Optional[tuple]:
    """If the offer lacks coords, geocode via Geoapify → Nominatim → FR_CITIES,
    persist the result, return (lat, lon) or None. No-op if coords already exist."""
    coords = _existing_coords(offer)
    if coords:
        return coords
    city = (offer.get("city") or "").strip()
    country = (offer.get("country") or "France").strip()
    if not city:
        return None
    address = offer.get("address") or city
    query = f"{address}, {country}" if address.lower() != country.lower() else address

    result = await geocode_geoapify(db, query, country)
    if not result:
        result = await geocode_nominatim(db, city, country)
    if not result:
        fr = geocode_french_city(city)
        if fr:
            result = (fr[0], fr[1], {"country": "France"})
    if not result:
        return None
    lat, lon, meta = result
    location = {
        "address": offer.get("address"),
        "city": meta.get("normalized_city") or city,
        "postal_code": meta.get("postal_code"),
        "country": meta.get("country") or country,
        "latitude": lat, "longitude": lon,
    }
    if offer.get("offer_id"):
        await db.offers.update_one(
            {"offer_id": offer["offer_id"]},
            {"$set": {"location": location, "latitude": lat, "longitude": lon}},
        )
    offer["location"] = location
    offer["latitude"] = lat
    offer["longitude"] = lon
    return lat, lon


def register_map_routes(api_router, db, get_current_user):
    @api_router.get("/offers-map")
    async def offers_map(
        country: Optional[str] = None,
        city: Optional[str] = None,
        contract_type: Optional[str] = None,
        domain: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 2000,
    ):
        query: dict = {"is_demo": {"$ne": True}}
        # Geocoded offers only: must have coords. We accept both styles
        # (top-level lat/lon or nested location.latitude).
        query["$or"] = [
            {"latitude": {"$type": "number"}, "longitude": {"$type": "number"}},
            {"location.latitude": {"$type": "number"}, "location.longitude": {"$type": "number"}},
            {"coords.lat": {"$type": "number"}, "coords.lon": {"$type": "number"}},
        ]
        if contract_type:
            query["contract_type"] = contract_type
        if domain:
            query["domain"] = {"$regex": domain, "$options": "i"}
        if q:
            query["$and"] = [{"$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"company_name": {"$regex": q, "$options": "i"}},
            ]}]

        offers = await db.offers.find(query, {"_id": 0}).limit(min(limit, 3000)).to_list(min(limit, 3000))
        out = []
        for o in offers:
            coords = _existing_coords(o)
            if not coords:
                continue
            if country:
                if normalize_text(country) not in normalize_text(o.get("country") or "France"):
                    continue
            if city:
                if normalize_text(city) not in normalize_text(o.get("city") or ""):
                    continue
            out.append({
                "id": o.get("offer_id"),
                "title": o.get("title"),
                "company": o.get("company_name"),
                "city": o.get("city"),
                "country": o.get("country") or "France",
                "latitude": coords[0],
                "longitude": coords[1],
                "contract_type": o.get("contract_type"),
                "domain": o.get("domain"),
                "url": o.get("external_url") or (f"/offers/{o['offer_id']}" if o.get("offer_id") else None),
                "is_external": bool(o.get("is_external")),
                "source": o.get("source"),
            })
        return {"count": len(out), "results": out}

    @api_router.post("/admin/offers/geocode-backfill")
    async def geocode_backfill(limit: int = 50, dry_run: bool = False,
                               user=Depends(get_current_user)):
        """Backfill `location.latitude/longitude` for offers missing coords.
        Rate-limited to ~5 req/s to respect Geoapify free tier (3000 req/day).
        """
        if user["role"] != "admin":
            raise HTTPException(403, "Admin uniquement")
        cursor = db.offers.find({
            "is_demo": {"$ne": True},
            "$nor": [
                {"latitude": {"$type": "number"}, "longitude": {"$type": "number"}},
                {"location.latitude": {"$type": "number"}},
                {"coords.lat": {"$type": "number"}},
            ],
            "city": {"$nin": [None, ""]},
        }, {"_id": 0}).limit(max(1, min(limit, 500)))
        offers = await cursor.to_list(max(1, min(limit, 500)))
        scanned = len(offers)
        geocoded = 0
        skipped = 0
        for o in offers:
            if dry_run:
                continue
            try:
                res = await ensure_offer_coords(db, o)
                if res:
                    geocoded += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"backfill geocode failed for offer {o.get('offer_id')}: {e}")
                skipped += 1
            await asyncio.sleep(0.2)  # ~5 req/s
        return {"scanned": scanned, "geocoded": geocoded, "skipped": skipped, "dry_run": dry_run}

    register_map_routes.ensure_offer_coords = ensure_offer_coords  # type: ignore[attr-defined]
