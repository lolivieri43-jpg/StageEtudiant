"""Geocoding helpers + routes — split from server.py.

Provides:
- CITY_COORDS legacy dict
- haversine(lat1, lon1, lat2, lon2)
- get_coords(city) — sync lookup (legacy dict → FR_CITIES)
- get_coords_async(city, country) — async, adds Nominatim/OSM fallback (cached 30 d)

Endpoints:
- GET /api/cities    — list known city names
- GET /api/geocode   — resolve a city to (lat, lon) + meta, returns found=false otherwise
- GET /api/offers-nearby — geo-radius search on db.offers
"""
from __future__ import annotations

import math
from typing import Optional

from fastapi import HTTPException


# Static mapping of major French cities → (lat, lng) — kept for backward compat
CITY_COORDS = {
    "paris": (48.8566, 2.3522), "marseille": (43.2965, 5.3698), "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442), "nice": (43.7102, 7.2620), "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521), "montpellier": (43.6108, 3.8767), "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573), "rennes": (48.1173, -1.6778), "reims": (49.2583, 4.0317),
    "saint-étienne": (45.4397, 4.3872), "toulon": (43.1242, 5.9280), "le havre": (49.4944, 0.1079),
    "grenoble": (45.1885, 5.7245), "dijon": (47.3220, 5.0415), "angers": (47.4784, -0.5632),
    "nîmes": (43.8367, 4.3601), "villeurbanne": (45.7720, 4.8902), "saint-denis": (48.9362, 2.3574),
    "le mans": (48.0061, 0.1996), "aix-en-provence": (43.5297, 5.4474), "clermont-ferrand": (45.7772, 3.0870),
    "brest": (48.3905, -4.4860), "tours": (47.3941, 0.6848), "amiens": (49.8941, 2.2958),
    "limoges": (45.8336, 1.2611), "annecy": (45.8992, 6.1294), "perpignan": (42.6886, 2.8948),
    "boulogne-billancourt": (48.8352, 2.2412), "besançon": (47.2378, 6.0241), "orléans": (47.9029, 1.9039),
    "metz": (49.1193, 6.1757), "rouen": (49.4432, 1.0993), "mulhouse": (47.7508, 7.3359),
    "caen": (49.1829, -0.3707), "nancy": (48.6921, 6.1844), "poitiers": (46.5802, 0.3404),
    "versailles": (48.8049, 2.1204), "la rochelle": (46.1591, -1.1517), "pau": (43.2951, -0.3708),
    "bourges": (47.0810, 2.3988), "ajaccio": (41.9192, 8.7386), "bastia": (42.7028, 9.4503),
    "belfort": (47.6379, 6.8628), "quimper": (47.9960, -4.0978), "lorient": (47.7484, -3.3702),
    "saint-denis (réunion)": (-20.8823, 55.4504), "cannes": (43.5528, 7.0174), "tourcoing": (50.7235, 3.1602),
    "roubaix": (50.6927, 3.1746), "nanterre": (48.8924, 2.2069),
}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_coords(city: Optional[str]):
    if not city:
        return None
    legacy = CITY_COORDS.get(city.strip().lower())
    if legacy:
        return legacy
    try:
        from geo_search import geocode_french_city as _gfc
        c = _gfc(city)
        if c:
            return c
    except Exception:
        pass
    return None


def register_geocoding_routes(api_router, db, enrich_offers_with_premium):
    async def get_coords_async(city: Optional[str], country: str = "France"):
        if not city:
            return None
        local = get_coords(city)
        if local:
            return local
        try:
            from geo_search import geocode_nominatim as _gn
            res = await _gn(db, city, country)
            if res:
                return (res[0], res[1])
        except Exception:
            pass
        return None

    register_geocoding_routes.get_coords_async = get_coords_async  # type: ignore[attr-defined]
    register_geocoding_routes.get_coords = get_coords  # type: ignore[attr-defined]
    register_geocoding_routes.haversine = haversine  # type: ignore[attr-defined]

    @api_router.get("/cities")
    async def list_cities():
        from geo_search import FR_CITIES
        all_cities = set(
            [c.title() for c in CITY_COORDS.keys()] + [c.title() for c in FR_CITIES.keys()],
        )
        all_cities.discard("Europe")
        return {"cities": sorted(all_cities)}

    @api_router.get("/geocode")
    async def geocode_city(city: str, country: str = "France"):
        from geo_search import geocode_french_city, geocode_nominatim
        local = geocode_french_city(city)
        if local:
            return {
                "found": True, "source": "local",
                "latitude": local[0], "longitude": local[1],
                "normalized_city": city.title(), "country": "France",
            }
        result = await geocode_nominatim(db, city, country)
        if not result:
            return {
                "found": False,
                "message": "Ville introuvable, vérifiez l'orthographe ou élargissez la recherche.",
            }
        lat, lon, meta = result
        return {"found": True, "source": "nominatim",
                "latitude": lat, "longitude": lon, **meta}

    @api_router.get("/offers-nearby")
    async def offers_nearby(city: str, distance_km: float = 50, limit: int = 200,
                            contract_type: Optional[str] = None,
                            source: Optional[str] = None):
        coords = await get_coords_async(city)
        if not coords:
            raise HTTPException(404,
                f"Ville introuvable: {city}. Vérifiez l'orthographe ou élargissez la recherche.",
            )
        lat0, lon0 = coords
        query: dict = {}
        if contract_type: query["contract_type"] = contract_type
        if source: query["source"] = source
        offers = await db.offers.find(query, {"_id": 0}).to_list(2000)
        result = []
        for o in offers:
            oc = get_coords(o.get("city"))
            if not oc:
                continue
            d = haversine(lat0, lon0, oc[0], oc[1])
            if d <= distance_km:
                o["distance_km"] = round(d, 1)
                result.append(o)
        result.sort(key=lambda x: x["distance_km"])
        result = result[:limit]
        await enrich_offers_with_premium(result)
        return result
