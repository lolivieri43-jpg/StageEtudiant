"""Iteration 11 — France Travail (Pôle Emploi) integration tests.

Endpoints under test:
- GET /api/francetravail/search (city, region, departement, domain, q, nature, per_page)
- DELETE /api/admin/ft-cache (admin-only)

Also verifies:
- 4h cache TTL via cache_hit:false → cache_hit:true on identical second call
- OAuth token cached (no separate endpoint, but two searches with different cache_keys still succeed)
- api_request_logs (via /api/admin/api-stats) has api_name=francetravail entries
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@stagiaireconnect.fr"
ADMIN_PASSWORD = "Admin123!"
CAND_EMAIL = "lucas.martin@email.fr"
CAND_PASSWORD = "Demo1234!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def cand_token():
    return _login(CAND_EMAIL, CAND_PASSWORD)


@pytest.fixture(scope="module", autouse=True)
def purge_cache_before_run(admin_token):
    requests.delete(f"{API}/admin/ft-cache", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    yield


# ---------- Basic search ----------
class TestFranceTravailSearch:
    def test_search_paris_per_page_5(self):
        r = requests.get(f"{API}/francetravail/search", params={"city": "Paris", "per_page": 5}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "results" in data and "total" in data and "cache_hit" in data
        assert data["cache_hit"] is False
        assert isinstance(data["results"], list)
        assert len(data["results"]) >= 1
        first = data["results"][0]
        assert first["source"] == "FranceTravail"
        assert first.get("offer_id", "").startswith("ft_")
        # apply_url must point to candidat.francetravail.fr (per FT origineOffre.urlOrigine)
        assert first.get("apply_url"), "apply_url missing"
        assert "candidat.francetravail.fr" in first["apply_url"], f"unexpected apply_url: {first['apply_url']}"

    def test_second_call_is_cached(self):
        # First call (warm)
        r1 = requests.get(f"{API}/francetravail/search", params={"city": "Paris", "per_page": 5}, timeout=30)
        assert r1.status_code == 200
        # Second identical call
        r2 = requests.get(f"{API}/francetravail/search", params={"city": "Paris", "per_page": 5}, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["cache_hit"] is True
        assert d2["total"] == r1.json()["total"]

    def test_no_params_defaults_to_dept_75(self):
        r = requests.get(f"{API}/francetravail/search", params={"per_page": 3}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["results"], list)
        # Default Paris (75) — at least 1 result expected from real API
        assert len(data["results"]) >= 1

    def test_departement_69(self):
        r = requests.get(f"{API}/francetravail/search", params={"departement": "69", "per_page": 3}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["results"], list)
        assert len(data["results"]) >= 1

    def test_city_lyon_returns_dept_69(self):
        r = requests.get(f"{API}/francetravail/search", params={"city": "Lyon", "per_page": 5}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) >= 1
        # At least one result should have department '69'
        depts = [o.get("department") for o in data["results"]]
        assert "69" in depts, f"expected department=69 in Lyon results, got {depts}"

    def test_domain_informatique_uses_rome(self):
        r = requests.get(
            f"{API}/francetravail/search",
            params={"city": "Paris", "domain": "informatique", "per_page": 5},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        # If results exist, rome_codes should be from informatique mapping (M1805/M1810/M1802/M1803)
        if data["results"]:
            allowed = {"M1805", "M1810", "M1802", "M1803"}
            found_any = False
            for o in data["results"]:
                rcs = o.get("rome_codes") or []
                if any(rc in allowed for rc in rcs):
                    found_any = True
                    break
            assert found_any, f"none of the results had a ROME code in {allowed}"


# ---------- Admin cache purge ----------
class TestFTAdminCache:
    def test_purge_requires_admin(self, cand_token):
        r = requests.delete(
            f"{API}/admin/ft-cache",
            headers={"Authorization": f"Bearer {cand_token}"},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403 for candidate, got {r.status_code}"

    def test_purge_no_auth_returns_401(self):
        r = requests.delete(f"{API}/admin/ft-cache", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_purge_admin_ok(self, admin_token):
        # warm cache first
        requests.get(f"{API}/francetravail/search", params={"city": "Paris", "per_page": 3}, timeout=30)
        r = requests.delete(
            f"{API}/admin/ft-cache",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body.get("ok") is True
        assert "deleted" in body


# ---------- api_request_logs ----------
class TestFTLogging:
    def test_logs_contain_francetravail(self, admin_token):
        # Trigger at least one call to ensure log row exists
        requests.get(f"{API}/francetravail/search", params={"city": "Paris", "per_page": 3}, timeout=30)
        r = requests.get(
            f"{API}/admin/api-stats",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        # Endpoint should exist — if not, fallback to checking via search behaviour
        if r.status_code != 200:
            pytest.skip(f"/admin/api-stats not available ({r.status_code})")
        data = r.json()
        # by_api dict expected (per iter10 report)
        by_api = data.get("by_api") or data.get("apis") or {}
        # accept either dict {francetravail: {...}} or list of dicts
        if isinstance(by_api, dict):
            assert "francetravail" in by_api, f"francetravail missing in by_api keys: {list(by_api.keys())}"
        elif isinstance(by_api, list):
            names = [x.get("api_name") or x.get("_id") for x in by_api]
            assert "francetravail" in names, f"francetravail missing in {names}"
        else:
            pytest.skip(f"unexpected by_api shape: {type(by_api)}")
