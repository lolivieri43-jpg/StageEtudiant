"""Iter7 Phase B — External company search (Annuaire/Recherche d'Entreprises) integration tests."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@stagiaireconnect.fr", "password": "Admin123!"}
COMPANY = {"email": "hr@brightstudio011.fr", "password": "Demo1234!"}
CANDIDATE = {"email": "lucas.martin@email.fr", "password": "Demo1234!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def company_token():
    return _login(COMPANY)


@pytest.fixture(scope="module")
def candidate_token():
    return _login(CANDIDATE)


# ============ /companies/search ============
class TestCompaniesSearch:
    def test_search_no_criteria_returns_400(self):
        r = requests.get(f"{API}/companies/search", timeout=15)
        assert r.status_code == 400
        body = r.json()
        assert "détail" in body or "detail" in body
        msg = (body.get("detail") or body.get("détail") or "").lower()
        assert "critère" in msg or "critere" in msg

    def test_search_by_q_returns_normalized(self):
        r = requests.get(f"{API}/companies/search", params={"q": "technova", "per_page": 2}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        for key in ("results", "total", "page", "per_page", "cache_hit"):
            assert key in data, f"missing key {key}"
        assert isinstance(data["results"], list)
        # If results found, validate normalized fields
        if data["results"]:
            row = data["results"][0]
            for f in ("name", "siret", "city", "region", "naf_code", "address"):
                assert f in row, f"missing normalized field {f}"

    def test_search_caching_second_call_hits_cache(self):
        params = {"q": "technova", "per_page": 2}
        r1 = requests.get(f"{API}/companies/search", params=params, timeout=20)
        assert r1.status_code == 200
        # first might be cache_hit True if previously cached — force a unique q to ensure first call is fresh
        unique_q = f"technova{int(time.time())}"
        r1 = requests.get(f"{API}/companies/search", params={"q": unique_q, "per_page": 2}, timeout=20)
        assert r1.status_code == 200
        assert r1.json()["cache_hit"] is False
        r2 = requests.get(f"{API}/companies/search", params={"q": unique_q, "per_page": 2}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["cache_hit"] is True, "Second identical call should hit cache"

    def test_search_by_code_postal(self):
        r = requests.get(f"{API}/companies/search", params={"code_postal": "69003", "per_page": 2}, timeout=20)
        assert r.status_code == 200
        assert "results" in r.json()

    def test_search_by_departement(self):
        r = requests.get(f"{API}/companies/search", params={"departement": "69", "per_page": 2}, timeout=20)
        assert r.status_code == 200
        assert "results" in r.json()

    def test_search_by_region_84(self):
        r = requests.get(f"{API}/companies/search", params={"region": "84", "per_page": 2}, timeout=20)
        assert r.status_code == 200
        assert "results" in r.json()

    def test_search_by_naf(self):
        r = requests.get(f"{API}/companies/search", params={"activite_principale": "62.01Z", "per_page": 2}, timeout=20)
        assert r.status_code == 200
        assert "results" in r.json()


# ============ /companies/siret/{siret} ============
class TestCompanyBySiret:
    def test_get_invalid_siret_404(self):
        r = requests.get(f"{API}/companies/siret/INVALID", timeout=15)
        assert r.status_code == 404

    def test_get_valid_siret_and_cached(self):
        # First find a real SIRET via search
        s = requests.get(f"{API}/companies/search", params={"q": "decathlon", "per_page": 5}, timeout=20).json()
        siret = None
        for row in s.get("results", []):
            if row.get("siret"):
                siret = row["siret"]
                break
        if not siret:
            pytest.skip("No SIRET available from search to test detail endpoint")
        r1 = requests.get(f"{API}/companies/siret/{siret}", timeout=20)
        assert r1.status_code == 200, r1.text[:200]
        body = r1.json()
        assert body.get("siret") == siret
        assert "name" in body
        # Second call cached (no public cache_hit flag, but second call should be fast — just assert 200)
        r2 = requests.get(f"{API}/companies/siret/{siret}", timeout=10)
        assert r2.status_code == 200


# ============ /admin/external-cache ============
class TestAdminExternalCache:
    def test_list_cache_requires_admin(self, company_token):
        r = requests.get(f"{API}/admin/external-cache", headers={"Authorization": f"Bearer {company_token}"}, timeout=15)
        assert r.status_code == 403

    def test_list_cache_anonymous_401(self):
        r = requests.get(f"{API}/admin/external-cache", timeout=15)
        # No token -> 401 or 403 depending on auth dep
        assert r.status_code in (401, 403)

    def test_list_cache_admin(self, admin_token):
        # First ensure there's at least one cache entry
        requests.get(f"{API}/companies/search", params={"q": "carrefour", "per_page": 2}, timeout=20)
        r = requests.get(f"{API}/admin/external-cache", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("search_cache_count", "details_cache_count", "search_cache_entries", "details_cache_entries", "recent_logs", "recent_errors"):
            assert k in data, f"missing field {k}"
        assert isinstance(data["search_cache_count"], int)
        assert isinstance(data["recent_logs"], list)

    def test_refresh_cache_siret(self, admin_token):
        s = requests.get(f"{API}/companies/search", params={"q": "decathlon", "per_page": 3}, timeout=20).json()
        siret = next((r["siret"] for r in s.get("results", []) if r.get("siret")), None)
        if not siret:
            pytest.skip("No SIRET available to force refresh")
        r = requests.post(
            f"{API}/admin/external-cache/refresh",
            json={"kind": "siret", "siret": siret},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("siret") == siret

    def test_delete_cache_all(self, admin_token):
        # Ensure caches have some content
        requests.get(f"{API}/companies/search", params={"q": "leroymerlin", "per_page": 2}, timeout=20)
        r = requests.delete(
            f"{API}/admin/external-cache",
            params={"scope": "all"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert "deleted" in body
        assert "search" in body["deleted"] and "details" in body["deleted"]


# ============ profile-v2 new fields ============
class TestProfileV2NewFields:
    def test_company_can_set_new_directory_fields(self, company_token):
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "siren": "552120222",
            "postal_code": "59000",
            "naf_code": "62.01Z",
            "siret_verified": True,
            "siret_verified_at": now_iso,
        }
        r = requests.put(
            f"{API}/profile-v2",
            json=payload,
            headers={"Authorization": f"Bearer {company_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        prof = body.get("profile", {})
        assert prof.get("siren") == "552120222"
        assert prof.get("postal_code") == "59000"
        assert prof.get("naf_code") == "62.01Z"
        assert prof.get("siret_verified") is True
        assert prof.get("siret_verified_at") == now_iso

    def test_get_me_has_new_fields(self, company_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {company_token}"}, timeout=15)
        assert r.status_code == 200
        prof = r.json().get("profile", {})
        # Persistence
        assert prof.get("siren") == "552120222"
        assert prof.get("naf_code") == "62.01Z"


# ============ logs ============
class TestApiLogs:
    def test_logs_created_after_call(self, admin_token):
        # Trigger one fresh search
        unique_q = f"logcheck{int(time.time())}"
        requests.get(f"{API}/companies/search", params={"q": unique_q, "per_page": 1}, timeout=20)
        r = requests.get(f"{API}/admin/external-cache", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200
        logs = r.json().get("recent_logs", [])
        assert any(unique_q in str(L.get("query", {})) for L in logs), "Expected fresh log entry for unique query"
