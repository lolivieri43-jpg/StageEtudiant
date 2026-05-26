"""External job aggregator — KEYED APIs (Phase H).

Sources implemented:
- Adzuna:  https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?app_id&app_key&what&where
- Jooble:  POST https://jooble.org/api/{api_key}  body: {"keywords":"...", "location":"...", "page": 1}
- EURES via Apify actor:
    POST https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={APIFY_TOKEN}

All return normalized StageEtudiant offer dicts. Caching is handled by the orchestrator (12h).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

KEYWORDS = [
    "intern", "internship", "stage", "apprentice", "apprenticeship",
    "alternance", "junior", "étudiant", "trainee", "graduate",
]


def _is_relevant(title: str, description: str = "") -> bool:
    if not title:
        return False
    txt = f"{title} {description}".lower()
    return any(k in txt for k in KEYWORDS)


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"<[^>]+>", " ", s)[:5000]


def _contract_type(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ["alternance", "apprentice", "apprenti"]):
        return "alternance"
    if any(w in t for w in ["stage", "intern", "trainee"]):
        return "stage"
    return "emploi"


async def _http_get(url: str, params: Optional[dict] = None, timeout: int = 15) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    try:
        r = await loop.run_in_executor(
            None,
            lambda: requests.get(
                url,
                params=params,
                headers={"Accept": "application/json",
                         "User-Agent": "StageEtudiant/1.0 (contact@stageetudiant.fr)"},
                timeout=timeout,
            ),
        )
        if r.status_code != 200:
            logger.warning(f"GET {url} → HTTP {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"GET {url} → {e}")
        return None


async def _http_post(url: str, json_body: dict, timeout: int = 30) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    try:
        r = await loop.run_in_executor(
            None,
            lambda: requests.post(
                url,
                json=json_body,
                headers={"Accept": "application/json",
                         "Content-Type": "application/json",
                         "User-Agent": "StageEtudiant/1.0 (contact@stageetudiant.fr)"},
                timeout=timeout,
            ),
        )
        if r.status_code not in (200, 201):
            logger.warning(f"POST {url} → HTTP {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"POST {url} → {e}")
        return None


# ============ ADZUNA ============
async def fetch_adzuna(what: str = "stage alternance", where: str = "France",
                       country: str = "fr", pages: int = 2,
                       results_per_page: int = 50) -> List[Dict]:
    """Fetch jobs from Adzuna for France by default. Free tier: ~250 calls/month.

    Adzuna response shape:
      {"count": N, "results": [{id, title, description, redirect_url,
                                 company:{display_name}, location:{display_name, area:[...]} , created, ...}]}
    """
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []

    all_out: List[Dict] = []
    for page in range(1, max(1, pages) + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": what,
            "where": where,
            "results_per_page": min(results_per_page, 50),
            "content-type": "application/json",
        }
        data = await _http_get(url, params=params)
        if not data:
            break
        for j in data.get("results", []) or []:
            title = j.get("title") or ""
            desc = _strip_html(j.get("description") or "")
            if not _is_relevant(title, desc):
                continue
            loc = (j.get("location") or {}).get("display_name") or ""
            area = (j.get("location") or {}).get("area") or []
            city_guess = area[-1] if area else (loc.split(",")[0].strip() if loc else None)
            region_guess = area[1] if len(area) > 1 else None
            redirect = j.get("redirect_url")
            all_out.append({
                "offer_id": f"adz_{j.get('id') or uuid.uuid4().hex[:8]}",
                "title": title,
                "description": desc,
                "contract_type": _contract_type(title + " " + desc),
                "experience_type": "alternance" if "alternance" in (title + desc).lower() else "stage",
                "company_name": (j.get("company") or {}).get("display_name"),
                "company_id": None,
                "city": city_guess,
                "region": region_guess,
                "country": "France" if country == "fr" else country.upper(),
                "latitude": j.get("latitude"),
                "longitude": j.get("longitude"),
                "apply_url": redirect,
                "external_url": redirect,
                "source": "Adzuna",
                "internal": False, "external": True, "is_external": True,
                "is_demo": False, "source_verified": True, "api_provider": "Adzuna",
                "source_priority": 5,
                "category": (j.get("category") or {}).get("label"),
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "created_at": j.get("created") or datetime.now(timezone.utc).isoformat(),
            })
        if len(data.get("results", []) or []) < results_per_page:
            break
    return all_out


# ============ JOOBLE ============
async def fetch_jooble(keywords: str = "stage alternance",
                       location: str = "France", page: int = 1) -> List[Dict]:
    """Jooble REST API. Free quota ~500 calls/day."""
    key = os.environ.get("JOOBLE_API_KEY")
    if not key:
        return []
    url = f"https://jooble.org/api/{key}"
    body = {"keywords": keywords, "location": location, "page": page}
    data = await _http_post(url, body)
    if not data:
        return []
    out: List[Dict] = []
    for j in data.get("jobs", []) or []:
        title = j.get("title") or ""
        desc = _strip_html(j.get("snippet") or "")
        if not _is_relevant(title, desc):
            continue
        loc = j.get("location") or ""
        out.append({
            "offer_id": f"job_{j.get('id') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc + " " + (j.get("type") or "")),
            "experience_type": "alternance" if "alternance" in (title + desc).lower() else "stage",
            "company_name": j.get("company"),
            "company_id": None,
            "city": loc.split(",")[0].strip() if loc else None,
            "region": None,
            "country": "France" if "france" in loc.lower() else None,
            "latitude": None, "longitude": None,
            "apply_url": j.get("link"),
            "external_url": j.get("link"),
            "source": "Jooble",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "Jooble",
            "source_priority": 5,
            "created_at": j.get("updated") or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ EURES (via Apify actor) ============
async def fetch_eures_apify(country_codes: Optional[List[str]] = None,
                            keywords: str = "stage alternance internship",
                            max_items: int = 100) -> List[Dict]:
    """Run the EURES Apify scraper synchronously.
    Returns dataset items (list of jobs)."""
    token = os.environ.get("APIFY_TOKEN")
    actor = os.environ.get("APIFY_EURES_ACTOR", "lexis-solutions~eures-eu-jobs-scraper")
    if not token:
        return []
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"
    body = {
        "keywords": keywords,
        "countryCodes": country_codes or ["FR", "BE", "LU", "DE", "ES", "IT"],
        "maxItems": max_items,
    }
    data = await _http_post(url, body, timeout=90)
    if not data or not isinstance(data, list):
        return []
    out: List[Dict] = []
    for j in data:
        title = j.get("title") or j.get("jobTitle") or ""
        desc = _strip_html(j.get("description") or j.get("descriptionFull") or "")
        if not _is_relevant(title, desc):
            continue
        loc = j.get("location") or j.get("city") or ""
        out.append({
            "offer_id": f"eu_{j.get('id') or uuid.uuid4().hex[:10]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "alternance" if "alternance" in (title + desc).lower() else "stage",
            "company_name": j.get("employer") or j.get("companyName") or j.get("company"),
            "company_id": None,
            "city": (loc.split(",")[0].strip() if isinstance(loc, str) else None),
            "region": j.get("region"),
            "country": j.get("country") or j.get("countryCode"),
            "latitude": None, "longitude": None,
            "apply_url": j.get("url") or j.get("applyUrl") or j.get("link"),
            "external_url": j.get("url") or j.get("link"),
            "source": "EURES",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "EURES",
            "source_priority": 4,
            "created_at": j.get("publicationDate") or j.get("createdAt") or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ ORCHESTRATOR ============
async def fetch_all_keyed(db, force_refresh: bool = False,
                          what: str = "stage alternance",
                          where: str = "France") -> Dict:
    """Fetch from all keyed sources in parallel + cache 12h."""
    now = datetime.now(timezone.utc)
    cache_key = f"keyed_{what}_{where}".lower()
    cache_doc = await db.external_offers_cache.find_one({"key": cache_key}, {"_id": 0})
    if not force_refresh and cache_doc and cache_doc.get("expires_at"):
        try:
            exp = datetime.fromisoformat(cache_doc["expires_at"].replace("Z", "+00:00"))
            if exp > now:
                return {
                    "results": cache_doc.get("results", []),
                    "cache_hit": True,
                    "by_source": cache_doc.get("by_source", {}),
                }
        except Exception:
            pass

    tasks = [
        fetch_adzuna(what=what, where=where),
        fetch_jooble(keywords=what, location=where),
    ]
    # Only call Apify if token present (it consumes credits)
    if os.environ.get("APIFY_TOKEN"):
        tasks.append(fetch_eures_apify(keywords=what))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_offers: List[Dict] = []
    by_source: Dict[str, int] = {}
    errors: List[str] = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
            continue
        if isinstance(r, list):
            for o in r:
                by_source[o["source"]] = by_source.get(o["source"], 0) + 1
            all_offers.extend(r)

    # dedupe by external_url
    seen, deduped = set(), []
    for o in all_offers:
        k = o.get("external_url") or o.get("offer_id")
        if k in seen:
            continue
        seen.add(k)
        deduped.append(o)

    await db.external_offers_cache.update_one(
        {"key": cache_key},
        {"$set": {
            "key": cache_key,
            "results": deduped,
            "by_source": by_source,
            "errors": errors,
            "cached_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=12)).isoformat(),
        }},
        upsert=True,
    )
    return {"results": deduped, "cache_hit": False, "by_source": by_source, "errors": errors}
