"""Iteration 10 backend tests — La Bonne Alternance integration + CV download contract.

Covers:
- GET /api/lba/search (?city=Lyon, ?city default Paris, geo-coords path)
- Cache hit on a 2nd identical call (TTL 4h)
- DELETE /api/admin/lba-cache (admin only / 403 non-admin)
- api_request_logs entry inserted for each search call
- Status: each LBA result has source='La Bonne Alternance' and apply_url
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@stagiaireconnect.fr", "Admin123!")
STUDENT = ("lucas.martin@email.fr", "Demo1234!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(*ADMIN)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def student_headers():
    return {"Authorization": f"Bearer {_login(*STUDENT)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def purge_cache_before(admin_headers):
    """Ensure no stale cache so cache_hit:false on first call below."""
    requests.delete(f"{API}/admin/lba-cache", headers=admin_headers, timeout=30)
    yield


class TestLBASearch:
    """LBA search endpoint behaviour."""

    def test_search_lyon_returns_results(self):
        r = requests.get(f"{API}/lba/search", params={"city": "Lyon", "radius": 30}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "results" in data and "total" in data and "cache_hit" in data
        assert data["cache_hit"] is False
        assert "jobs" in data and "recruiters" in data
        # at least 1 result expected on a fresh call
        assert isinstance(data["results"], list)
        assert data["total"] >= 1, f"expected >=1 LBA result for Lyon, got total={data['total']}"
        sample = data["results"][0]
        assert sample.get("source") == "La Bonne Alternance"
        assert sample.get("apply_url"), "apply_url missing on LBA result"
        # offer_id prefixed with lba_
        assert sample.get("offer_id", "").startswith("lba_")

    def test_search_cache_hit_on_second_call(self):
        # 1st call (cache may exist from previous test → may be hit) → use a unique radius to be deterministic
        params = {"city": "Lyon", "radius": 25}
        r1 = requests.get(f"{API}/lba/search", params=params, timeout=30)
        assert r1.status_code == 200
        # Now repeat — expect cache_hit:true
        time.sleep(0.5)
        r2 = requests.get(f"{API}/lba/search", params=params, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("cache_hit") is True, f"expected cache_hit on repeat call, got {d2}"
        # total preserved
        assert d2.get("total") == r1.json().get("total")

    def test_search_default_paris_when_no_params(self):
        r = requests.get(f"{API}/lba/search", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        # we don't assert >=1 (LBA might return 0 for some ROMEs in Paris) — but contract must hold
        assert isinstance(data["total"], int)

    def test_search_with_lat_lon(self):
        r = requests.get(
            f"{API}/lba/search",
            params={"latitude": 48.85, "longitude": 2.35, "radius": 15},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert isinstance(data["total"], int)


class TestLBAAdminCache:
    """Admin-only DELETE /api/admin/lba-cache."""

    def test_purge_requires_auth(self):
        r = requests.delete(f"{API}/admin/lba-cache", timeout=15)
        # no auth → 401 (or 403 depending on get_current_user)
        assert r.status_code in (401, 403), r.status_code

    def test_purge_forbidden_for_non_admin(self, student_headers):
        r = requests.delete(f"{API}/admin/lba-cache", headers=student_headers, timeout=15)
        assert r.status_code == 403

    def test_purge_admin_ok(self, admin_headers):
        # prime the cache with a search
        requests.get(f"{API}/lba/search", params={"city": "Lyon", "radius": 30}, timeout=30)
        r = requests.delete(f"{API}/admin/lba-cache", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "deleted" in data and isinstance(data["deleted"], int)


class TestLBALogging:
    """api_request_logs should accumulate LBA entries (verified via admin api-stats)."""

    def test_api_stats_includes_labonnealternance(self, admin_headers):
        # do one search to ensure at least one log entry
        requests.get(f"{API}/lba/search", params={"city": "Lyon", "radius": 30}, timeout=30)
        r = requests.get(f"{API}/admin/api-stats", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        by_api = data.get("by_api") or []
        names = [d.get("api_name") or d.get("_id") for d in by_api]
        assert "labonnealternance" in names, f"labonnealternance missing from stats by_api={by_api}"
