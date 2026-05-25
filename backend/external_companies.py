"""External companies — Annuaire / Recherche d'Entreprises (gouv.fr) integration.

Public open-data API, no auth key required.
Docs: https://recherche-entreprises.api.gouv.fr/docs/

Provides:
- normalized search and detail records
- in-DB caching (7d for searches, 30d for details)
- request/error logs
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import asyncio
import uuid
import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://recherche-entreprises.api.gouv.fr"
SEARCH_TTL_DAYS = 7
DETAIL_TTL_DAYS = 30

# Region INSEE code → name (subset)
REGION_NAMES = {
    "11": "Île-de-France", "24": "Centre-Val de Loire", "27": "Bourgogne-Franche-Comté",
    "28": "Normandie", "32": "Hauts-de-France", "44": "Grand Est", "52": "Pays de la Loire",
    "53": "Bretagne", "75": "Nouvelle-Aquitaine", "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes", "93": "Provence-Alpes-Côte d'Azur", "94": "Corse",
    "01": "Guadeloupe", "02": "Martinique", "03": "Guyane", "04": "La Réunion", "06": "Mayotte",
}


def _normalize_etab(siege: dict) -> dict:
    return {
        "siret": siege.get("siret"),
        "address": siege.get("adresse"),
        "postal_code": siege.get("code_postal"),
        "city": siege.get("libelle_commune"),
        "department": siege.get("departement"),
        "region_code": siege.get("region"),
        "region": REGION_NAMES.get(siege.get("region"), ""),
        "latitude": _to_float(siege.get("latitude")),
        "longitude": _to_float(siege.get("longitude")),
        "naf_code": siege.get("activite_principale"),
        "etat_administratif": siege.get("etat_administratif"),
        "date_creation": siege.get("date_creation"),
    }


def _to_float(v):
    try: return float(v) if v not in (None, "") else None
    except Exception: return None


def normalize_company(raw: dict) -> dict:
    """Map raw API result → flat StageConnect-style external company doc."""
    siege = raw.get("siege") or {}
    etab = _normalize_etab(siege)
    return {
        "siren": raw.get("siren"),
        "name": raw.get("nom_complet") or raw.get("nom_raison_sociale"),
        "legal_name": raw.get("nom_raison_sociale"),
        "trading_name": raw.get("sigle"),
        "active": raw.get("etat_administratif") == "A",
        "category": raw.get("categorie_entreprise"),
        "tranche_effectif": raw.get("tranche_effectif_salarie"),
        "naf_code": raw.get("activite_principale") or etab.get("naf_code"),
        "siret": etab.get("siret"),
        "address": etab.get("address"),
        "postal_code": etab.get("postal_code"),
        "city": etab.get("city"),
        "department": etab.get("department"),
        "region_code": etab.get("region_code"),
        "region": etab.get("region"),
        "latitude": etab.get("latitude"),
        "longitude": etab.get("longitude"),
        "date_creation": etab.get("date_creation"),
        "etablissements_count": raw.get("nombre_etablissements"),
        "etablissements_open_count": raw.get("nombre_etablissements_ouverts"),
        "source": "annuaire_entreprises",
    }


async def _log_request(db, endpoint: str, query: dict, status: int, response_ms: int, hit_cache: bool):
    try:
        await db.api_request_logs.insert_one({
            "log_id": f"apilog_{uuid.uuid4().hex[:10]}",
            "api_name": "annuaire_entreprises",
            "endpoint": endpoint,
            "query": query,
            "status": status,
            "response_time_ms": response_ms,
            "cache_hit": bool(hit_cache),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"api_request_log failed: {e}")


async def _log_error(db, endpoint: str, query: dict, error: str):
    try:
        await db.api_error_logs.insert_one({
            "log_id": f"apierr_{uuid.uuid4().hex[:10]}",
            "api_name": "annuaire_entreprises",
            "endpoint": endpoint,
            "query": query,
            "error": error[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


def _cache_key(params: dict) -> str:
    parts = sorted(f"{k}={v}" for k, v in params.items() if v not in (None, ""))
    return "|".join(parts)


async def search_companies(db, *, q: Optional[str] = None, code_postal: Optional[str] = None,
                           departement: Optional[str] = None, region: Optional[str] = None,
                           activite_principale: Optional[str] = None, page: int = 1,
                           per_page: int = 10, force_refresh: bool = False) -> Dict:
    """Search via Recherche d'Entreprises API with DB cache."""
    params = {
        "q": q or "", "code_postal": code_postal, "departement": departement,
        "region": region, "activite_principale": activite_principale,
        "page": page, "per_page": min(per_page, 25),
    }
    key = _cache_key(params)
    now = datetime.now(timezone.utc)

    if not force_refresh:
        cached = await db.external_company_search_cache.find_one(
            {"cache_key": key}, {"_id": 0}
        )
        if cached and cached.get("expires_at"):
            try:
                exp = datetime.fromisoformat(cached["expires_at"].replace("Z", "+00:00"))
                if exp > now:
                    await _log_request(db, "/search", params, 200, 0, hit_cache=True)
                    return {
                        "results": cached.get("results", []),
                        "total": cached.get("total", 0),
                        "page": page,
                        "per_page": per_page,
                        "cache_hit": True,
                        "cached_at": cached.get("cached_at"),
                    }
            except Exception:
                pass

    started = datetime.now(timezone.utc)
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    try:
        # Use run_in_executor to avoid blocking
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(None, lambda: requests.get(f"{BASE_URL}/search", params=clean, timeout=10))
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        await _log_request(db, "/search", clean, r.status_code, elapsed, hit_cache=False)
        if r.status_code != 200:
            await _log_error(db, "/search", clean, f"HTTP {r.status_code}: {r.text[:200]}")
            return {"results": [], "total": 0, "page": page, "per_page": per_page, "cache_hit": False, "error": f"HTTP {r.status_code}"}
        data = r.json() or {}
        raw_results = data.get("results", [])
        normalized = [normalize_company(x) for x in raw_results]
        total = data.get("total_results", len(normalized))
        await db.external_company_search_cache.update_one(
            {"cache_key": key},
            {"$set": {
                "cache_key": key,
                "query": params,
                "results": normalized,
                "total": total,
                "results_count": len(normalized),
                "source_api": "annuaire_entreprises",
                "cached_at": now.isoformat(),
                "expires_at": (now + timedelta(days=SEARCH_TTL_DAYS)).isoformat(),
            }, "$setOnInsert": {"cache_id": f"cs_{uuid.uuid4().hex[:10]}"}},
            upsert=True,
        )
        return {"results": normalized, "total": total, "page": page, "per_page": per_page, "cache_hit": False}
    except Exception as e:
        await _log_error(db, "/search", clean, str(e))
        return {"results": [], "total": 0, "page": page, "per_page": per_page, "cache_hit": False, "error": str(e)}


async def get_company_by_siret(db, siret: str, force_refresh: bool = False) -> Optional[dict]:
    """Fetch details by SIRET (14 digits) — cached 30d."""
    siret = (siret or "").replace(" ", "")
    if len(siret) < 9:
        return None
    now = datetime.now(timezone.utc)
    if not force_refresh:
        cached = await db.external_company_details_cache.find_one({"siret": siret}, {"_id": 0})
        if cached and cached.get("expires_at"):
            try:
                exp = datetime.fromisoformat(cached["expires_at"].replace("Z", "+00:00"))
                if exp > now:
                    await _log_request(db, "/search", {"q": siret}, 200, 0, hit_cache=True)
                    return cached["data"]
            except Exception:
                pass
    # The public search endpoint accepts SIREN/SIRET directly in `q`
    started = datetime.now(timezone.utc)
    try:
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(None, lambda: requests.get(f"{BASE_URL}/search", params={"q": siret, "per_page": 1}, timeout=10))
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        await _log_request(db, "/search", {"q": siret}, r.status_code, elapsed, hit_cache=False)
        if r.status_code != 200:
            await _log_error(db, "/search", {"q": siret}, f"HTTP {r.status_code}")
            return None
        data = r.json() or {}
        results = data.get("results", [])
        if not results:
            return None
        normalized = normalize_company(results[0])
        await db.external_company_details_cache.update_one(
            {"siret": siret},
            {"$set": {
                "siret": siret,
                "data": normalized,
                "source_api": "annuaire_entreprises",
                "cached_at": now.isoformat(),
                "expires_at": (now + timedelta(days=DETAIL_TTL_DAYS)).isoformat(),
            }, "$setOnInsert": {"cache_id": f"cd_{uuid.uuid4().hex[:10]}"}},
            upsert=True,
        )
        return normalized
    except Exception as e:
        await _log_error(db, "/search", {"q": siret}, str(e))
        return None
