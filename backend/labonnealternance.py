"""La Bonne Alternance — official French apprenticeship/internship API.

Docs: https://api.apprentissage.beta.gouv.fr/
Auth: Bearer token (env LBA_API_TOKEN).

Provides:
- /jobs/search by ROME codes + lat/long + radius
- Cached results (4h) to avoid repeated calls
- Normalization to StageConnect's offer shape so existing components can render them
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import asyncio
import os
import uuid
import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.apprentissage.beta.gouv.fr"
DEFAULT_ROMES = "M1805,M1810,M1802,M1803,E1101,E1103,K1207,K1801,M1707,M1701,M1402,M1502"
CACHE_TTL_HOURS = 4


def _token() -> Optional[str]:
    return os.environ.get("LBA_API_TOKEN")


def normalize_lba_job(raw: dict, kind: str = "job") -> Dict:
    """Map a La Bonne Alternance entry → StageConnect offer-like dict."""
    wp = raw.get("workplace") or {}
    loc = wp.get("location") or {}
    coords = (loc.get("geopoint") or {}).get("coordinates") or []
    naf = (wp.get("domain") or {}).get("naf") or {}
    offer = raw.get("offer") or {}
    contract = raw.get("contract") or {}
    apply_ = raw.get("apply") or {}
    identifier = raw.get("identifier") or {}
    # extract city from "address" like "322 RUE DES PYRENEES 75020 PARIS"
    addr = loc.get("address") or ""
    city = ""
    postal_code = ""
    # naive postal code + city extraction
    import re
    m = re.search(r"\b(\d{5})\b\s+([A-ZÀ-Ÿ' \-]+)$", addr.strip())
    if m:
        postal_code = m.group(1)
        city = m.group(2).strip().title()
    return {
        "offer_id": f"lba_{identifier.get('id') or uuid.uuid4().hex[:10]}",
        "title": (offer.get("title") or wp.get("name") or "Alternance / Apprentissage"),
        "description": (offer.get("description") or ""),
        "contract_type": "alternance",
        "experience_type": (contract.get("type") or ["Apprentissage"])[0].lower() if isinstance(contract.get("type"), list) else "alternance",
        "company_name": wp.get("name") or wp.get("legal_name"),
        "company_logo": None,
        "company_id": None,
        "city": city or None,
        "postal_code": postal_code or None,
        "region": None,  # not provided by LBA; can be computed from postal_code if needed
        "department": (postal_code[:2] if postal_code else None),
        "latitude": coords[1] if len(coords) >= 2 else None,
        "longitude": coords[0] if len(coords) >= 2 else None,
        "naf_code": naf.get("code"),
        "naf_label": naf.get("label"),
        "siret": wp.get("siret"),
        "size": wp.get("size"),
        "apply_url": apply_.get("url"),
        "source": "La Bonne Alternance",
        "internal": False,
        "external": True,
        "kind": kind,
        "rome_codes": offer.get("rome_codes") or [],
        "skills": offer.get("rome_codes") or [],
        "publication_date": (offer.get("publication_date") or raw.get("created_at")),
        "created_at": (offer.get("publication_date") or raw.get("created_at") or datetime.now(timezone.utc).isoformat()),
    }


async def _log(db, endpoint: str, params: dict, status: int, ms: int, hit_cache: bool):
    try:
        await db.api_request_logs.insert_one({
            "log_id": f"apilog_{uuid.uuid4().hex[:10]}",
            "api_name": "labonnealternance",
            "endpoint": endpoint,
            "query": params,
            "status": status,
            "response_time_ms": ms,
            "cache_hit": bool(hit_cache),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"lba log failed: {e}")


def _cache_key(p: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(p.items()) if v not in (None, ""))


async def search_alternance(
    db,
    *,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius: int = 30,
    romes: str = DEFAULT_ROMES,
    per_page: int = 30,
    force_refresh: bool = False,
) -> Dict:
    """Search alternance offers from La Bonne Alternance.

    Geo (lat/long) is recommended for relevance — if missing, default Paris is used.
    """
    if latitude is None or longitude is None:
        # default Paris if no geo provided
        latitude, longitude = 48.8566, 2.3522
    params = {
        "latitude": round(float(latitude), 4),
        "longitude": round(float(longitude), 4),
        "radius": int(radius or 30),
        "romes": romes,
    }
    key = _cache_key(params)
    now = datetime.now(timezone.utc)
    if not force_refresh:
        cached = await db.lba_search_cache.find_one({"cache_key": key}, {"_id": 0})
        if cached and cached.get("expires_at"):
            try:
                exp = datetime.fromisoformat(cached["expires_at"].replace("Z", "+00:00"))
                if exp > now:
                    await _log(db, "/jobs/search", params, 200, 0, hit_cache=True)
                    return {
                        "results": cached.get("results", []),
                        "total": cached.get("total", 0),
                        "cache_hit": True,
                        "cached_at": cached.get("cached_at"),
                    }
            except Exception:
                pass
    tok = _token()
    if not tok:
        logger.warning("LBA_API_TOKEN missing in env")
        return {"results": [], "total": 0, "cache_hit": False, "error": "Token absent"}
    started = datetime.now(timezone.utc)
    try:
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(
            None,
            lambda: requests.get(
                f"{BASE_URL}/api/job/v1/search",
                params=params,
                headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                timeout=15,
            ),
        )
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        await _log(db, "/jobs/search", params, r.status_code, elapsed, hit_cache=False)
        if r.status_code != 200:
            await db.api_error_logs.insert_one({
                "log_id": f"lbaerr_{uuid.uuid4().hex[:8]}",
                "api_name": "labonnealternance",
                "endpoint": "/jobs/search",
                "query": params,
                "error": f"HTTP {r.status_code}: {r.text[:300]}",
                "created_at": now.isoformat(),
            })
            return {"results": [], "total": 0, "cache_hit": False, "error": f"HTTP {r.status_code}"}
        data = r.json() or {}
        jobs = [normalize_lba_job(x, "job") for x in (data.get("jobs") or [])]
        recruiters = [normalize_lba_job(x, "recruiter") for x in (data.get("recruiters") or [])]
        # only keep top per_page, jobs first then recruiters
        all_results = (jobs + recruiters)[: int(per_page)]
        total = len(jobs) + len(recruiters)
        await db.lba_search_cache.update_one(
            {"cache_key": key},
            {
                "$set": {
                    "cache_key": key,
                    "query": params,
                    "results": all_results,
                    "total": total,
                    "cached_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=CACHE_TTL_HOURS)).isoformat(),
                },
                "$setOnInsert": {"cache_id": f"lba_{uuid.uuid4().hex[:10]}"},
            },
            upsert=True,
        )
        return {"results": all_results, "total": total, "cache_hit": False, "jobs": len(jobs), "recruiters": len(recruiters)}
    except Exception as e:
        await db.api_error_logs.insert_one({
            "log_id": f"lbaerr_{uuid.uuid4().hex[:8]}",
            "api_name": "labonnealternance",
            "endpoint": "/jobs/search",
            "query": params,
            "error": str(e),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"results": [], "total": 0, "cache_hit": False, "error": str(e)}
