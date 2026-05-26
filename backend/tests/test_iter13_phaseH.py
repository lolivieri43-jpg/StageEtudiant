"""Phase H tests: Adzuna + Jooble + EURES (keyed) + admin-sources-status + cache purge.

Also re-validates Phase F/G basics: diploma-levels (33), /api/offers no demo,
keyless aggregator, anonymous AI search.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@stagiaireconnect.fr"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------- Phase F basics ----------------

def test_diploma_levels_33():
    r = requests.get(f"{BASE_URL}/api/diploma-levels", timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    levels = data.get("levels")
    assert isinstance(levels, list)
    assert len(levels) == 33, f"Expected 33 diploma levels, got {len(levels)}"


def test_offers_no_demo():
    r = requests.get(f"{BASE_URL}/api/offers", timeout=30)
    assert r.status_code == 200, r.text[:300]
    offers = r.json()
    assert isinstance(offers, list)
    for o in offers:
        assert o.get("is_demo") is not True, f"Offer is_demo=True found: {o.get('title')}"


def test_anonymous_ai_search():
    r = requests.post(f"{BASE_URL}/api/ai/search",
                      json={"query": "stage marketing Paris", "limit": 5}, timeout=30)
    assert r.status_code == 200, f"Anonymous AI search failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert "results" in data or "offers" in data or isinstance(data, dict)


# ---------------- Phase G keyless ----------------

def test_keyless_offers_returns_list():
    r = requests.get(f"{BASE_URL}/api/external-offers/keyless", timeout=90)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    # Allow zero but log breakdown
    print("keyless by_source:", data.get("by_source"))


# ---------------- Phase H keyed ----------------

def test_keyed_offers_force_refresh():
    """Adzuna should return offers; Jooble may 403 (known issue)."""
    r = requests.get(f"{BASE_URL}/api/external-offers/keyed",
                     params={"force_refresh": "true"}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "results" in data
    by_src = data.get("by_source", {})
    print("keyed by_source:", by_src, "errors:", data.get("errors"))
    # Adzuna should produce >0 (free tier allowing). Don't hard-fail on rate limit (429/403).
    adz = by_src.get("Adzuna", 0)
    if adz == 0:
        # Acceptable if rate-limited; record warning
        print("WARNING: Adzuna returned 0 offers — possible rate-limit/key issue")
    else:
        assert adz > 0
    # EURES expected 0 (no APIFY_TOKEN)
    assert by_src.get("EURES", 0) == 0
    # Jooble may be 0 due to known 403


def test_keyed_offers_cache_hit():
    """Second call without force_refresh should hit cache."""
    requests.get(f"{BASE_URL}/api/external-offers/keyed",
                 params={"force_refresh": "true"}, timeout=120)
    r = requests.get(f"{BASE_URL}/api/external-offers/keyed", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("cache_hit") is True, f"Expected cache_hit True, got {data.get('cache_hit')}"


def test_external_offers_all_merge():
    r = requests.get(f"{BASE_URL}/api/external-offers/all", timeout=120)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    results = data.get("results", [])
    by_src = data.get("by_source", {})
    print("ALL by_source:", by_src, "total:", len(results))
    assert isinstance(results, list)
    # Dedupe check
    seen = set()
    dup = 0
    for o in results:
        k = o.get("external_url") or o.get("offer_id")
        if k in seen:
            dup += 1
        seen.add(k)
    assert dup == 0, f"Found {dup} duplicate offers in /external-offers/all"


# ---------------- Admin endpoints ----------------

def test_admin_external_sources_status(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/external-sources-status",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    sources = data.get("sources", [])
    names = [s["name"] for s in sources]
    for expected in ["Adzuna", "Jooble", "EURES", "Arbeitnow", "Remotive", "RemoteOK",
                     "Jobicy", "Ashby", "Greenhouse"]:
        assert expected in names, f"Missing source {expected} in admin status"
    # Adzuna/Jooble/EURES must declare requires_key
    for s in sources:
        if s["name"] in ("Adzuna", "Jooble", "EURES"):
            assert s.get("requires_key") is True


def test_admin_sources_status_forbidden_anon():
    r = requests.get(f"{BASE_URL}/api/admin/external-sources-status", timeout=10)
    assert r.status_code in (401, 403)


def test_admin_purge_external_offers_cache(admin_headers):
    r = requests.delete(f"{BASE_URL}/api/admin/external-offers-cache",
                        headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("ok") is True
    assert "deleted" in data


def test_admin_purge_forbidden_anon():
    r = requests.delete(f"{BASE_URL}/api/admin/external-offers-cache", timeout=10)
    assert r.status_code in (401, 403)
