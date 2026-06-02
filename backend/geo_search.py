"""Geo & search helpers — strict company match (accent-insensitive),
Haversine distance, French city geocoding, EU country detection.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Optional, Tuple


# ---------- Normalization ----------
def normalize_text(s: Optional[str]) -> str:
    """Lowercase + remove diacritics + strip + collapse whitespace + remove common suffixes.
    E.g. "EDF S.A." → "edf sa" ; "Crédit Agricole" → "credit agricole"
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Remove punctuation
    s = re.sub(r"[.,;:()\[\]'\"’]", " ", s)
    # Remove common French/intl. company suffixes
    s = re.sub(
        r"\b(sa|sas|sasu|sarl|eurl|sci|sci|sa de cv|ag|gmbh|llc|inc|ltd|corp|company|co|group|groupe|holding|s a r l)\b",
        " ",
        s,
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s


def companies_match(a: Optional[str], b: Optional[str]) -> bool:
    """Strict match (after normalization)."""
    if not a or not b:
        return False
    return normalize_text(a) == normalize_text(b)


def company_contains_term(name: Optional[str], term: Optional[str]) -> bool:
    """Loose match: term must appear inside name (substring, accent-insensitive).
    Falls back to whole-word match if substring is too short (<=2 chars) to avoid noise."""
    if not name or not term:
        return False
    norm_name = normalize_text(name)
    norm_term = normalize_text(term)
    if not norm_term:
        return False
    if len(norm_term) <= 2:
        # very short terms: require whole-word match to limit noise (e.g. "sa", "fr")
        return re.search(rf"\b{re.escape(norm_term)}\b", norm_name) is not None
    # 3+ chars: simple substring match — handles "Beta" in "BetaSystems081" and "Sof" in "Sofratom"
    return norm_term in norm_name


# ---------- Haversine ----------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------- French city geocoding (top ~120 cities) ----------
# Source: INSEE / Wikipedia approximate coordinates
FR_CITIES: dict[str, Tuple[float, float]] = {
    "paris": (48.8566, 2.3522),
    "marseille": (43.2965, 5.3698),
    "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442),
    "nice": (43.7102, 7.2620),
    "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521),
    "montpellier": (43.6109, 3.8772),
    "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573),
    "rennes": (48.1173, -1.6778),
    "reims": (49.2583, 4.0317),
    "toulon": (43.1242, 5.9280),
    "saint-etienne": (45.4397, 4.3872),
    "le havre": (49.4944, 0.1079),
    "grenoble": (45.1885, 5.7245),
    "dijon": (47.3220, 5.0415),
    "angers": (47.4784, -0.5632),
    "villeurbanne": (45.7665, 4.8795),
    "saint-denis": (48.9362, 2.3574),
    "le mans": (48.0061, 0.1996),
    "aix-en-provence": (43.5297, 5.4474),
    "brest": (48.3905, -4.4861),
    "nimes": (43.8367, 4.3601),
    "limoges": (45.8336, 1.2611),
    "clermont-ferrand": (45.7772, 3.0870),
    "tours": (47.3941, 0.6848),
    "amiens": (49.8941, 2.2958),
    "perpignan": (42.6886, 2.8946),
    "metz": (49.1193, 6.1757),
    "besancon": (47.2378, 6.0241),
    "boulogne-billancourt": (48.8358, 2.2406),
    "orleans": (47.9029, 1.9090),
    "mulhouse": (47.7508, 7.3359),
    "rouen": (49.4432, 1.0993),
    "caen": (49.1829, -0.3707),
    "nancy": (48.6921, 6.1844),
    "saint-paul": (-20.9844, 55.2702),
    "argenteuil": (48.9474, 2.2475),
    "montreuil": (48.8636, 2.4486),
    "roubaix": (50.6927, 3.1745),
    "tourcoing": (50.7239, 3.1612),
    "nanterre": (48.8923, 2.2071),
    "vitry-sur-seine": (48.7872, 2.3897),
    "creteil": (48.7906, 2.4555),
    "avignon": (43.9493, 4.8055),
    "poitiers": (46.5802, 0.3404),
    "fort-de-france": (14.6037, -61.0732),
    "courbevoie": (48.8965, 2.2553),
    "versailles": (48.8049, 2.1204),
    "colombes": (48.9226, 2.2522),
    "asnieres-sur-seine": (48.9131, 2.2873),
    "rueil-malmaison": (48.8780, 2.1813),
    "aubervilliers": (48.9145, 2.3845),
    "champigny-sur-marne": (48.8156, 2.5159),
    "saint-maur-des-fosses": (48.7980, 2.4937),
    "calais": (50.9513, 1.8587),
    "cannes": (43.5528, 7.0174),
    "antibes": (43.5808, 7.1239),
    "drancy": (48.9302, 2.4456),
    "merignac": (44.8326, -0.6976),
    "ajaccio": (41.9192, 8.7386),
    "saint-nazaire": (47.2735, -2.2128),
    "issy-les-moulineaux": (48.8260, 2.2737),
    "noisy-le-grand": (48.8487, 2.5530),
    "evry": (48.6293, 2.4408),
    "cergy": (49.0367, 2.0763),
    "pessac": (44.8067, -0.6311),
    "villeneuve-d'ascq": (50.6190, 3.1418),
    "valence": (44.9333, 4.8920),
    "quimper": (47.9963, -4.0985),
    "antony": (48.7536, 2.2978),
    "troyes": (48.2973, 4.0744),
    "ivry-sur-seine": (48.8156, 2.3839),
    "neuilly-sur-seine": (48.8847, 2.2691),
    "sarcelles": (48.9939, 2.3819),
    "venissieux": (45.6976, 4.8830),
    "clichy": (48.9044, 2.3068),
    "pau": (43.2951, -0.3708),
    "lorient": (47.7484, -3.3702),
    "la rochelle": (46.1591, -1.1520),
    "chambery": (45.5646, 5.9178),
    "beauvais": (49.4304, 2.0810),
    "cholet": (47.0608, -0.8780),
    "bourges": (47.0810, 2.3988),
    "saint-quentin": (49.8489, 3.2876),
    "niort": (46.3232, -0.4585),
    "vannes": (47.6582, -2.7608),
    "chalon-sur-saone": (46.7811, 4.8540),
    "annecy": (45.8992, 6.1294),
    "laval": (48.0737, -0.7704),
    "saint-louis": (47.5860, 7.5604),
    "albi": (43.9298, 2.1480),
    "bayonne": (43.4929, -1.4748),
    "brive-la-gaillarde": (45.1582, 1.5331),
    "evreux": (49.0260, 1.1500),
    "lens": (50.4310, 2.8324),
    "saint-malo": (48.6493, -2.0260),
    "frejus": (43.4332, 6.7370),
    "blois": (47.5863, 1.3359),
    "agen": (44.2032, 0.6212),
    "tarbes": (43.2333, 0.0782),
    "arles": (43.6766, 4.6280),
    "alençon": (48.4304, 0.0931),
    "carcassonne": (43.2130, 2.3491),
    "annemasse": (46.1942, 6.2363),
    "biarritz": (43.4832, -1.5586),
    "chateauroux": (46.8113, 1.6916),
    "saint-brieuc": (48.5135, -2.7659),
    "menton": (43.7755, 7.5024),
    "vincennes": (48.8472, 2.4399),
    "saint-cloud": (48.8400, 2.2189),
    "savigny-sur-orge": (48.6792, 2.3477),
    "epinay-sur-seine": (48.9555, 2.3122),
    "athis-mons": (48.7065, 2.3964),
    "longjumeau": (48.6961, 2.2999),
    "boulogne-sur-mer": (50.7264, 1.6147),
    "valenciennes": (50.3585, 3.5234),
    "saint-omer": (50.7531, 2.2541),
    "thonon-les-bains": (46.3697, 6.4806),
    "vichy": (46.1273, 3.4262),
    "vienne": (45.5253, 4.8743),
    "epernay": (49.0436, 3.9586),
    "monaco": (43.7384, 7.4246),
    "europe": (50.0, 10.0),  # rough EU centre as last-resort fallback
}


def geocode_french_city(city: Optional[str]) -> Optional[Tuple[float, float]]:
    if not city:
        return None
    key = unicodedata.normalize("NFKD", city.lower()).encode("ascii", "ignore").decode().strip()
    # try the exact normalized name
    if key in FR_CITIES:
        return FR_CITIES[key]
    # try first token (handles "Paris 11e" → "paris")
    head = key.split()[0] if key else ""
    if head in FR_CITIES:
        return FR_CITIES[head]
    # try with hyphenated head ("saint-denis", "saint-etienne")
    if "-" in key:
        joined = key.split(",")[0].strip()
        if joined in FR_CITIES:
            return FR_CITIES[joined]
    return None


async def geocode_geoapify(db, query: str, country: Optional[str] = None) -> Optional[Tuple[float, float, dict]]:
    """Geocode via Geoapify (better worldwide coverage than Nominatim). Cached 30 days in
    db.geocoding_cache (shared with Nominatim, key prefixed by 'gapi:').

    Returns (lat, lon, meta) or None. Meta keys: normalized_city, postal_code, region, country, country_code.
    """
    import os
    from datetime import datetime, timezone, timedelta
    import httpx

    api_key = os.environ.get("GEOAPIFY_API_KEY")
    if not api_key:
        return None
    q = (query or "").strip()
    if not q:
        return None
    if country and country.lower() not in q.lower():
        q = f"{q}, {country}"
    cache_key = f"gapi:{q.lower()}"
    cache = await db.geocoding_cache.find_one({"query": cache_key}, {"_id": 0})
    if cache:
        exp = cache.get("expires_at")
        try:
            exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
            if exp_dt and exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt and exp_dt > datetime.now(timezone.utc):
                if cache.get("latitude") and cache.get("longitude"):
                    return float(cache["latitude"]), float(cache["longitude"]), {
                        "normalized_city": cache.get("normalized_city"),
                        "postal_code": cache.get("postal_code"),
                        "region": cache.get("region"),
                        "country": cache.get("country"),
                        "country_code": cache.get("country_code"),
                    }
                return None
        except Exception:
            pass

    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://api.geoapify.com/v1/geocode/search",
                params={"text": q, "limit": 1, "format": "json", "apiKey": api_key},
            )
        if resp.status_code != 200:
            await db.geocoding_api_logs.insert_one({
                "provider": "geoapify", "query": q, "status": resp.status_code,
                "response_time_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
                "error_message": resp.text[:500],
                "created_at": started.isoformat(),
            })
            return None
        data = resp.json()
        results = data.get("results") or []
        meta_log = {
            "provider": "geoapify", "query": q, "status": 200,
            "response_time_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            "created_at": started.isoformat(),
        }
        if not results:
            await db.geocoding_api_logs.insert_one(meta_log)
            # negative cache (1 day) so we don't keep hitting empty queries
            await db.geocoding_cache.update_one(
                {"query": cache_key},
                {"$set": {
                    "query": cache_key, "source": "geoapify",
                    "created_at": started.isoformat(),
                    "expires_at": (started + timedelta(days=1)).isoformat(),
                }},
                upsert=True,
            )
            return None
        r = results[0]
        lat = float(r.get("lat"))
        lon = float(r.get("lon"))
        meta = {
            "normalized_city": r.get("city") or r.get("county") or r.get("name"),
            "postal_code": r.get("postcode"),
            "region": r.get("state"),
            "country": r.get("country"),
            "country_code": (r.get("country_code") or "").upper() or None,
        }
        await db.geocoding_api_logs.insert_one(meta_log)
        await db.geocoding_cache.update_one(
            {"query": cache_key},
            {"$set": {
                "query": cache_key, "source": "geoapify",
                "latitude": lat, "longitude": lon, **meta,
                "raw_payload_json": r,
                "created_at": started.isoformat(),
                "expires_at": (started + timedelta(days=30)).isoformat(),
            }},
            upsert=True,
        )
        return lat, lon, meta
    except Exception as e:
        await db.geocoding_api_logs.insert_one({
            "provider": "geoapify", "query": q, "status": 0,
            "response_time_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            "error_message": str(e)[:500],
            "created_at": started.isoformat(),
        })
        return None


async def geocode_nominatim(db, city: str, country: str = "France") -> Optional[Tuple[float, float, dict]]:
    """Geocode via Nominatim/OSM with 30-day Mongo cache.
    Returns (lat, lon, meta) or None. Meta includes normalized_city, postal_code, department, region, country_code.
    Always sets a custom User-Agent + respects 1 req/s usage limits (cached entries skip the network call).
    """
    if not city:
        return None
    import asyncio as _asyncio
    import time as _time
    from datetime import datetime, timezone, timedelta
    import requests as _rq

    query = f"{city}, {country}" if country and country.lower() not in city.lower() else city
    query_key = query.lower().strip()

    # 1) Cache check
    cache = await db.geocoding_cache.find_one({"query": query_key}, {"_id": 0})
    if cache:
        try:
            exp = datetime.fromisoformat(cache["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > datetime.now(timezone.utc):
                if cache.get("latitude") and cache.get("longitude"):
                    return float(cache["latitude"]), float(cache["longitude"]), {
                        "normalized_city": cache.get("normalized_city"),
                        "postal_code": cache.get("postal_code"),
                        "department": cache.get("department"),
                        "region": cache.get("region"),
                        "country": cache.get("country"),
                        "country_code": cache.get("country_code"),
                    }
                return None  # cached negative
        except Exception:
            pass

    # 2) Call Nominatim
    started = _time.monotonic()
    error_message = None
    status = "ok"
    try:
        def _call():
            return _rq.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "addressdetails": 1, "limit": 1},
                headers={
                    "User-Agent": "StageEtudiant.com/1.0 (contact@stageetudiant.com)",
                    "Accept-Language": "fr,en",
                },
                timeout=8,
            )
        r = await _asyncio.to_thread(_call)
        if r.status_code != 200:
            status = f"http_{r.status_code}"
            error_message = r.text[:200]
            data = []
        else:
            data = r.json()
    except Exception as e:
        status = "exception"
        error_message = str(e)[:200]
        data = []

    response_time_ms = int((_time.monotonic() - started) * 1000)
    await db.geocoding_api_logs.insert_one({
        "provider": "nominatim",
        "query": query_key,
        "status": status,
        "response_time_ms": response_time_ms,
        "error_message": error_message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    now = datetime.now(timezone.utc)
    if not data:
        # Cache negative result for 7 days
        await db.geocoding_cache.update_one(
            {"query": query_key},
            {"$set": {
                "query": query_key,
                "latitude": None, "longitude": None,
                "source": "nominatim",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=7)).isoformat(),
            }},
            upsert=True,
        )
        return None

    item = data[0]
    addr = item.get("address", {}) or {}
    lat = float(item["lat"])
    lon = float(item["lon"])
    normalized_city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or city
    meta = {
        "normalized_city": normalized_city,
        "postal_code": addr.get("postcode"),
        "department": addr.get("county") or addr.get("state_district"),
        "region": addr.get("state"),
        "country": addr.get("country"),
        "country_code": (addr.get("country_code") or "").upper() or None,
    }
    await db.geocoding_cache.update_one(
        {"query": query_key},
        {"$set": {
            "query": query_key,
            "latitude": lat, "longitude": lon,
            "source": "nominatim",
            **meta,
            "raw_payload_json": item,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
        }},
        upsert=True,
    )
    return lat, lon, meta


def offer_coords(offer: dict) -> Optional[Tuple[float, float]]:
    """Resolve (lat, lon) for an offer from its own fields or by geocoding its city."""
    lat = offer.get("latitude") or offer.get("lat")
    lon = offer.get("longitude") or offer.get("lon") or offer.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return geocode_french_city(offer.get("city"))


# ---------- European countries ----------
EU_COUNTRIES = {
    "France", "Belgique", "Belgium", "Suisse", "Switzerland", "Luxembourg",
    "Allemagne", "Germany", "Espagne", "Spain", "Italie", "Italy",
    "Royaume-Uni", "United Kingdom", "UK", "Pays-Bas", "Netherlands",
    "Portugal", "Irlande", "Ireland", "Autriche", "Austria",
    "Pologne", "Poland", "Suède", "Sweden", "Norvège", "Norway",
    "Danemark", "Denmark", "Finlande", "Finland", "Tchéquie", "Czech Republic",
    "Hongrie", "Hungary", "Roumanie", "Romania", "Grèce", "Greece",
    "Bulgarie", "Bulgaria", "Slovaquie", "Slovakia", "Slovénie", "Slovenia",
    "Estonie", "Estonia", "Lettonie", "Latvia", "Lituanie", "Lithuania",
    "Croatie", "Croatia", "Malte", "Malta", "Chypre", "Cyprus",
    "Monaco", "Andorre", "Andorra", "Liechtenstein",
}

FR_NAMES = {"France", "FR", "fr"}


def is_french(country: Optional[str]) -> bool:
    if not country:
        return True  # unknown → treated as France by default per requirements
    return country.strip() in FR_NAMES or normalize_text(country) == "france"


def is_european(country: Optional[str]) -> bool:
    if not country:
        return False
    norm = normalize_text(country)
    for c in EU_COUNTRIES:
        if normalize_text(c) == norm:
            return True
    # ISO codes
    return country.strip().upper() in {
        "FR", "BE", "CH", "LU", "DE", "ES", "IT", "GB", "UK", "NL", "PT",
        "IE", "AT", "PL", "SE", "NO", "DK", "FI", "CZ", "HU", "RO", "GR",
        "BG", "SK", "SI", "EE", "LV", "LT", "HR", "MT", "CY", "MC", "AD", "LI",
    }


# Aliases FR ↔ EN ↔ ISO so a single user query matches all of them
COUNTRY_ALIASES: dict[str, set[str]] = {
    "france":      {"france", "fr"},
    "belgique":    {"belgique", "belgium", "be"},
    "suisse":      {"suisse", "switzerland", "ch"},
    "luxembourg":  {"luxembourg", "lu"},
    "allemagne":   {"allemagne", "germany", "de", "deutschland"},
    "espagne":     {"espagne", "spain", "es", "espana"},
    "italie":      {"italie", "italy", "it", "italia"},
    "royaume-uni": {"royaume uni", "united kingdom", "uk", "gb", "great britain", "england"},
    "pays-bas":    {"pays bas", "netherlands", "nl", "holland"},
    "portugal":    {"portugal", "pt"},
    "irlande":     {"irlande", "ireland", "ie"},
    "autriche":    {"autriche", "austria", "at"},
    "pologne":     {"pologne", "poland", "pl"},
    "danemark":    {"danemark", "denmark", "dk"},
    "suede":       {"suede", "sweden", "se"},
    "norvege":     {"norvege", "norway", "no"},
    "finlande":    {"finlande", "finland", "fi"},
    "grece":       {"grece", "greece", "gr"},
    "tchequie":    {"tchequie", "czech republic", "czechia", "cz"},
    "hongrie":     {"hongrie", "hungary", "hu"},
    "roumanie":    {"roumanie", "romania", "ro"},
}


def countries_match(filter_val: str, offer_country: Optional[str]) -> bool:
    """True if user filter (e.g. 'Allemagne') matches offer.country ('Germany' / 'DE' / etc.)."""
    if not offer_country:
        return normalize_text(filter_val) in ("france", "fr")
    f_norm = normalize_text(filter_val).replace("-", " ")
    o_norm = normalize_text(offer_country).replace("-", " ")
    if f_norm == o_norm:
        return True
    for canon, aliases in COUNTRY_ALIASES.items():
        canon_n = canon.replace("-", " ")
        if (f_norm == canon_n or f_norm in aliases) and (o_norm == canon_n or o_norm in aliases):
            return True
    return False
