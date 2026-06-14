"""External job aggregator — keyless public APIs (Phase G).

Sources implemented:
- Ashby Job Postings: https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
- Arbeitnow:         https://www.arbeitnow.com/api/job-board-api
- Remotive:          https://remotive.com/api/remote-jobs
- RemoteOK:          https://remoteok.com/api  (User-Agent required, cache fortement)
- Jobicy:            https://jobicy.com/api/v2/remote-jobs
- Greenhouse:        https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

All return normalized StageEtudiant offer dicts. Caching is handled at server level (4-12h).
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict
import asyncio
import re
import uuid
import requests
import logging

logger = logging.getLogger(__name__)

KEYWORDS = ["intern", "internship", "stage", "apprentice", "apprenticeship",
            "alternance", "junior", "étudiant", "trainee", "graduate"]


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


async def _fetch(url: str, headers: Optional[dict] = None, timeout: int = 12) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    try:
        h = {"Accept": "application/json", "User-Agent": "StageEtudiant/1.0 (contact@stageetudiant.fr)"}
        if headers:
            h.update(headers)
        r = await loop.run_in_executor(None, lambda: requests.get(url, headers=h, timeout=timeout))
        if r.status_code != 200:
            logger.warning(f"{url} → HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"{url} → {e}")
        return None


# ============ ASHBY ============
async def fetch_ashby(board_token: str = "Ashby") -> List[Dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeCompensation=true"
    data = await _fetch(url)
    if not data:
        return []
    out = []
    for j in (data.get("jobs") or []):
        title = j.get("title") or ""
        desc = _strip_html(j.get("descriptionHtml") or "")
        if not _is_relevant(title, desc):
            continue
        loc = j.get("location") or ""
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or ""
        out.append({
            "offer_id": f"ashby_{j.get('id') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "alternance" if "alternance" in title.lower() else "stage",
            "company_name": data.get("organization", {}).get("name") or board_token,
            "company_id": None,
            "city": loc.split(",")[0].strip() if loc else None,
            "region": None,
            "country": country or "France",
            "latitude": None, "longitude": None,
            "apply_url": j.get("jobUrl") or j.get("applicationUrl"),
            "external_url": j.get("jobUrl"),
            "source": "Ashby",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "Ashby",
            "source_priority": 5,
            "published_at": j.get("publishedAt"),
            "created_at": j.get("publishedAt") or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ ARBEITNOW ============
async def fetch_arbeitnow() -> List[Dict]:
    data = await _fetch("https://www.arbeitnow.com/api/job-board-api")
    if not data:
        return []
    out = []
    for j in (data.get("data") or [])[:100]:
        title = j.get("title") or ""
        desc = _strip_html(j.get("description") or "")
        if not _is_relevant(title, desc):
            continue
        out.append({
            "offer_id": f"arbn_{j.get('slug') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "alternance" if "alternance" in title.lower() else "stage",
            "company_name": j.get("company_name"),
            "company_id": None,
            "city": j.get("location"),
            "region": None,
            "country": "France" if (j.get("location") or "").lower().find("france") >= 0 else None,
            "latitude": None, "longitude": None,
            "apply_url": j.get("url"),
            "external_url": j.get("url"),
            "source": "Arbeitnow",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "Arbeitnow",
            "source_priority": 4,
            "remote": bool(j.get("remote")),
            "tags": j.get("tags", []),
            "created_at": (j.get("created_at") and datetime.fromtimestamp(j["created_at"], tz=timezone.utc).isoformat()) or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ REMOTIVE ============
async def fetch_remotive() -> List[Dict]:
    data = await _fetch("https://remotive.com/api/remote-jobs?limit=100")
    if not data:
        return []
    out = []
    for j in (data.get("jobs") or []):
        title = j.get("title") or ""
        desc = _strip_html(j.get("description") or "")
        if not _is_relevant(title, desc):
            continue
        out.append({
            "offer_id": f"remv_{j.get('id') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "stage",
            "company_name": j.get("company_name"),
            "company_id": None,
            "city": j.get("candidate_required_location"),
            "region": None,
            "country": None,
            "latitude": None, "longitude": None,
            "apply_url": j.get("url"),
            "external_url": j.get("url"),
            "source": "Remotive",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "Remotive",
            "source_priority": 4,
            "remote": True,
            "category": j.get("category"),
            "tags": j.get("tags", []),
            "created_at": j.get("publication_date") or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ REMOTEOK ============
async def fetch_remoteok() -> List[Dict]:
    data = await _fetch("https://remoteok.com/api", headers={"User-Agent": "StageEtudiant/1.0"})
    if not data or not isinstance(data, list):
        return []
    out = []
    # 1st entry is metadata
    for j in data[1:]:
        title = j.get("position") or j.get("title") or ""
        desc = _strip_html(j.get("description") or "")
        if not _is_relevant(title, desc):
            continue
        out.append({
            "offer_id": f"rmok_{j.get('id') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "stage",
            "company_name": j.get("company"),
            "company_id": None,
            "city": j.get("location"),
            "region": None,
            "country": None,
            "latitude": None, "longitude": None,
            "apply_url": j.get("apply_url") or j.get("url"),
            "external_url": j.get("url"),
            "source": "RemoteOK",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "RemoteOK",
            "source_priority": 4,
            "remote": True,
            "tags": j.get("tags", []),
            "created_at": j.get("date") or datetime.now(timezone.utc).isoformat(),
        })
    return out[:80]


# ============ JOBICY ============
async def fetch_jobicy() -> List[Dict]:
    data = await _fetch("https://jobicy.com/api/v2/remote-jobs?count=100")
    if not data:
        return []
    out = []
    for j in (data.get("jobs") or []):
        title = j.get("jobTitle") or ""
        desc = _strip_html(j.get("jobExcerpt") or "")
        if not _is_relevant(title, desc):
            continue
        out.append({
            "offer_id": f"jbcy_{j.get('id') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "stage",
            "company_name": j.get("companyName"),
            "company_id": None,
            "city": (j.get("jobGeo") or "").split(",")[0] if j.get("jobGeo") else None,
            "region": None,
            "country": None,
            "latitude": None, "longitude": None,
            "apply_url": j.get("url"),
            "external_url": j.get("url"),
            "source": "Jobicy",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "Jobicy",
            "source_priority": 4,
            "remote": True,
            "category": j.get("jobIndustry"),
            "tags": j.get("jobType", []),
            "created_at": j.get("pubDate") or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ GREENHOUSE ============
async def fetch_greenhouse(board_token: str) -> List[Dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    data = await _fetch(url)
    if not data:
        return []
    out = []
    for j in (data.get("jobs") or []):
        title = j.get("title") or ""
        desc = _strip_html(j.get("content") or "")
        if not _is_relevant(title, desc):
            continue
        loc = (j.get("location") or {}).get("name") or ""
        out.append({
            "offer_id": f"grh_{j.get('id') or uuid.uuid4().hex[:8]}",
            "title": title,
            "description": desc,
            "contract_type": _contract_type(title + " " + desc),
            "experience_type": "alternance" if "alternance" in title.lower() else "stage",
            "company_name": data.get("name") or board_token,
            "company_id": None,
            "city": loc.split(",")[0].strip() if loc else None,
            "region": None,
            "country": None,
            "latitude": None, "longitude": None,
            "apply_url": j.get("absolute_url"),
            "external_url": j.get("absolute_url"),
            "source": "Greenhouse",
            "internal": False, "external": True, "is_external": True,
            "is_demo": False, "source_verified": True, "api_provider": "Greenhouse",
            "source_priority": 5,
            "created_at": j.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        })
    return out


# ============ ORCHESTRATOR ============
async def fetch_all_keyless(db, force_refresh: bool = False) -> Dict:
    """Fetch from all keyless sources in parallel + cache 12h."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cache_doc = await db.external_offers_cache.find_one({"key": "keyless_all"}, {"_id": 0})
    if not force_refresh and cache_doc and cache_doc.get("expires_at"):
        try:
            exp = datetime.fromisoformat(cache_doc["expires_at"].replace("Z", "+00:00"))
            if exp > now:
                return {"results": cache_doc.get("results", []), "cache_hit": True, "by_source": cache_doc.get("by_source", {})}
        except Exception:
            pass

    # Get configured boards
    ashby_docs = await db.ashby_boards.find({"active": True}, {"_id": 0, "board_token": 1}).to_list(20)
    gh_docs = await db.greenhouse_boards.find({"active": True}, {"_id": 0, "board_token": 1}).to_list(20)

    tasks = [fetch_arbeitnow(), fetch_remotive(), fetch_remoteok(), fetch_jobicy()]
    tasks += [fetch_ashby(d["board_token"]) for d in ashby_docs] or [fetch_ashby("Ashby")]
    tasks += [fetch_greenhouse(d["board_token"]) for d in gh_docs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_offers = []
    by_source: Dict[str, int] = {}
    for r in results:
        if isinstance(r, list):
            for o in r:
                by_source[o["source"]] = by_source.get(o["source"], 0) + 1
            all_offers.extend(r)

    # Cross-source dedupe (exact URL + fuzzy company/title/city).
    from dedup import dedupe_offers as _dedupe
    deduped = _dedupe(all_offers)

    await db.external_offers_cache.update_one(
        {"key": "keyless_all"},
        {"$set": {
            "key": "keyless_all",
            "results": deduped,
            "by_source": by_source,
            "cached_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=12)).isoformat(),
        }},
        upsert=True,
    )
    return {"results": deduped, "cache_hit": False, "by_source": by_source}
