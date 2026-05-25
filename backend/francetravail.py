"""France Travail (Pôle Emploi) — Offres d'emploi v2 API integration.

Docs: https://francetravail.io/data/api/offres-emploi
OAuth2 client_credentials flow.

For StageEtudiant we only fetch:
 - natureContrat=E2 (apprentissage)
 - natureContrat=FS (contrat de professionnalisation = alternance pro)
 - natureContrat=E1 (contrat travail) optionally, when stage filter is applied
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import os
import uuid
import asyncio
import requests
import logging

logger = logging.getLogger(__name__)

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
API_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2"
SCOPES = "api_offresdemploiv2 o2dsoffre"
CACHE_TTL_HOURS = 4

# Default nature: apprentissage + contrat pro (alternance)
DEFAULT_NATURE_ALTERNANCE = "E2,FS"

# Mapping ROME-like search by domain
DOMAIN_TO_ROME = {
    "informatique": "M1805,M1810,M1802,M1803",
    "communication": "E1101,E1103",
    "marketing": "M1705,M1707",
    "commerce": "D1402,D1404,D1408",
    "rh": "M1502,M1503",
    "finance": "M1201,M1206",
}

# ---------- Token cache ----------
_token_cache: Dict[str, object] = {"token": None, "exp": None}


async def _get_token() -> Optional[str]:
    cid = os.environ.get("FT_CLIENT_ID")
    sec = os.environ.get("FT_CLIENT_SECRET")
    if not cid or not sec:
        logger.error("FT credentials missing")
        return None
    now = datetime.now(timezone.utc)
    cached = _token_cache.get("token")
    exp = _token_cache.get("exp")
    if cached and exp and exp > now + timedelta(seconds=60):
        return cached
    loop = asyncio.get_event_loop()
    try:
        r = await loop.run_in_executor(
            None,
            lambda: requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": cid,
                    "client_secret": sec,
                    "scope": SCOPES,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            ),
        )
        if r.status_code != 200:
            logger.error(f"FT token fetch failed: {r.status_code} {r.text[:300]}")
            return None
        data = r.json()
        tok = data.get("access_token")
        expires_in = int(data.get("expires_in", 1500))
        _token_cache["token"] = tok
        _token_cache["exp"] = now + timedelta(seconds=expires_in)
        logger.info(f"FT token refreshed (expires in {expires_in}s)")
        return tok
    except Exception as e:
        logger.error(f"FT token exception: {e}")
        return None


# ---------- Normalize ----------
def normalize_ft_offer(raw: dict) -> dict:
    lt = raw.get("lieuTravail") or {}
    ent = raw.get("entreprise") or {}
    origine = raw.get("origineOffre") or {}
    contact = raw.get("contact") or {}
    contract_type = "alternance" if (raw.get("alternance") or raw.get("natureContrat", "").lower().startswith("contrat apprentissage")
                                     or raw.get("natureContrat") in ("E2", "FS")) else (
        "stage" if raw.get("natureContrat") in ("E1", "FA") and raw.get("typeContrat") in ("CDD",) else
        (raw.get("typeContrat") or "").lower()
    )
    return {
        "offer_id": f"ft_{raw.get('id')}",
        "title": raw.get("intitule") or "Offre France Travail",
        "description": (raw.get("description") or "")[:5000],
        "contract_type": contract_type,
        "experience_type": "alternance" if (raw.get("alternance") or raw.get("natureContrat") in ("E2", "FS")) else "stage",
        "company_name": ent.get("nom") or "Entreprise non communiquée",
        "company_logo": ent.get("logo"),
        "company_id": None,
        "city": (lt.get("libelle") or "").split(" - ", 1)[-1] if lt.get("libelle") else None,
        "postal_code": lt.get("codePostal"),
        "department": (lt.get("commune") or "")[:2] if lt.get("commune") else None,
        "region": None,
        "latitude": lt.get("latitude"),
        "longitude": lt.get("longitude"),
        "naf_code": raw.get("codeNAF"),
        "naf_label": raw.get("secteurActiviteLibelle"),
        "siret": None,
        "size": None,
        "apply_url": origine.get("urlOrigine"),
        "external_url": origine.get("urlOrigine"),
        "source": "FranceTravail",
        "internal": False,
        "external": True,
        "kind": "job",
        "rome_codes": [raw.get("romeCode")] if raw.get("romeCode") else [],
        "rome_label": raw.get("romeLibelle"),
        "skills": [c.get("libelle") for c in (raw.get("competences") or []) if c.get("libelle")],
        "salary": (raw.get("salaire") or {}).get("libelle"),
        "duration": raw.get("typeContratLibelle"),
        "created_at": raw.get("dateCreation") or datetime.now(timezone.utc).isoformat(),
        "publication_date": raw.get("dateCreation"),
    }


# ---------- Logs ----------
async def _log(db, endpoint: str, params: dict, status: int, ms: int, hit_cache: bool):
    try:
        await db.api_request_logs.insert_one({
            "log_id": f"ft_{uuid.uuid4().hex[:10]}",
            "api_name": "francetravail",
            "endpoint": endpoint,
            "query": params,
            "status": status,
            "response_time_ms": ms,
            "cache_hit": bool(hit_cache),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def _log_error(db, endpoint: str, params: dict, error: str):
    try:
        await db.api_error_logs.insert_one({
            "log_id": f"fterr_{uuid.uuid4().hex[:8]}",
            "api_name": "francetravail",
            "endpoint": endpoint,
            "query": params,
            "error": error[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


def _cache_key(p: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(p.items()) if v not in (None, ""))


# ---------- Search ----------
async def search_offers(
    db,
    *,
    departement: Optional[str] = None,
    commune: Optional[str] = None,  # INSEE commune (5 digits)
    distance: int = 30,
    mots_cles: Optional[str] = None,
    rome: Optional[str] = None,
    domain: Optional[str] = None,
    nature_contrat: str = DEFAULT_NATURE_ALTERNANCE,
    per_page: int = 30,
    force_refresh: bool = False,
) -> Dict:
    """Search FT offers (default = alternance only)."""
    params = {
        "natureContrat": nature_contrat,
        "range": f"0-{max(0, min(per_page, 50) - 1)}",
    }
    if departement: params["departement"] = departement
    if commune:
        params["commune"] = commune
        params["distance"] = int(distance)
    if mots_cles: params["motsCles"] = mots_cles
    if rome: params["codeROME"] = rome
    elif domain and domain.lower() in DOMAIN_TO_ROME:
        params["codeROME"] = DOMAIN_TO_ROME[domain.lower()]

    key = _cache_key(params)
    now = datetime.now(timezone.utc)
    if not force_refresh:
        cached = await db.ft_search_cache.find_one({"cache_key": key}, {"_id": 0})
        if cached and cached.get("expires_at"):
            try:
                exp = datetime.fromisoformat(cached["expires_at"].replace("Z", "+00:00"))
                if exp > now:
                    await _log(db, "/offres/search", params, 200, 0, hit_cache=True)
                    return {
                        "results": cached.get("results", []),
                        "total": cached.get("total", 0),
                        "cache_hit": True,
                        "cached_at": cached.get("cached_at"),
                    }
            except Exception:
                pass

    tok = await _get_token()
    if not tok:
        return {"results": [], "total": 0, "cache_hit": False, "error": "OAuth token unavailable"}

    started = datetime.now(timezone.utc)
    try:
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(
            None,
            lambda: requests.get(
                f"{API_URL}/offres/search",
                params=params,
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Accept": "application/json",
                },
                timeout=15,
            ),
        )
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        await _log(db, "/offres/search", params, r.status_code, elapsed, hit_cache=False)
        # 200=full data; 206=partial content (range), still valid
        if r.status_code not in (200, 206):
            await _log_error(db, "/offres/search", params, f"HTTP {r.status_code}: {r.text[:300]}")
            return {"results": [], "total": 0, "cache_hit": False, "error": f"HTTP {r.status_code}"}
        data = r.json() or {}
        raw_results = data.get("resultats") or []
        normalized = [normalize_ft_offer(x) for x in raw_results]
        # Content-Range: "offres 0-2/N" → total = N
        total = len(normalized)
        cr = r.headers.get("Content-Range") or ""
        try:
            if "/" in cr:
                total = int(cr.split("/")[-1])
        except Exception:
            pass
        await db.ft_search_cache.update_one(
            {"cache_key": key},
            {
                "$set": {
                    "cache_key": key,
                    "query": params,
                    "results": normalized,
                    "total": total,
                    "results_count": len(normalized),
                    "cached_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=CACHE_TTL_HOURS)).isoformat(),
                },
                "$setOnInsert": {"cache_id": f"ft_{uuid.uuid4().hex[:10]}"},
            },
            upsert=True,
        )
        return {"results": normalized, "total": total, "cache_hit": False}
    except Exception as e:
        await _log_error(db, "/offres/search", params, str(e))
        return {"results": [], "total": 0, "cache_hit": False, "error": str(e)}
