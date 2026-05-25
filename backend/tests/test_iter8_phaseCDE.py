"""Tests for Phase C (student company lists), Phase D (AI search, history),
Phase E (admin api-stats)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CANDIDATE = ("lucas.martin@email.fr", "Demo1234!")
COMPANY = ("hr@brightstudio011.fr", "Demo1234!")
ADMIN = ("admin@stagiaireconnect.fr", "Admin123!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def candidate_token():
    return _login(*CANDIDATE)


@pytest.fixture(scope="module")
def company_token():
    return _login(*COMPANY)


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- Phase C: /me/companies ----------
class TestMyCompanies:
    @classmethod
    def setup_class(cls):
        # Clean up any prior tracking with TEST_ prefix
        tok = _login(*CANDIDATE)
        items = requests.get(f"{API}/me/companies", headers=H(tok), timeout=10).json()
        for it in items:
            if (it.get("name") or "").startswith("TEST_"):
                requests.delete(f"{API}/me/companies/{it['id']}", headers=H(tok), timeout=10)

    def test_add_company_candidate(self, candidate_token):
        body = {"name": "TEST_AlphaCorp", "siret": "TEST_SIRET_AAA", "city": "Lyon",
                "naf_code": "62.01Z"}
        r = requests.post(f"{API}/me/companies", json=body, headers=H(candidate_token), timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        assert data.get("name") == "TEST_AlphaCorp"
        assert data.get("status") == "a_contacter"
        TestMyCompanies.created_id = data["id"]

    def test_add_duplicate(self, candidate_token):
        body = {"name": "TEST_AlphaCorp", "siret": "TEST_SIRET_AAA"}
        r = requests.post(f"{API}/me/companies", json=body, headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("duplicate") is True
        assert data.get("id") == TestMyCompanies.created_id

    def test_company_role_forbidden(self, company_token):
        r = requests.post(f"{API}/me/companies", json={"name": "TEST_X"}, headers=H(company_token), timeout=10)
        assert r.status_code == 403

    def test_list_companies_filter(self, candidate_token):
        # add second item with different status
        body = {"name": "TEST_BetaInc", "siret": "TEST_SIRET_BBB"}
        rb = requests.post(f"{API}/me/companies", json=body, headers=H(candidate_token), timeout=10)
        bid = rb.json()["id"]
        # change status of beta to cv_envoye
        ru = requests.patch(f"{API}/me/companies/{bid}",
                            json={"status": "cv_envoye"}, headers=H(candidate_token), timeout=10)
        assert ru.status_code == 200
        # filter by status
        r = requests.get(f"{API}/me/companies?status=a_contacter", headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        names = [x["name"] for x in r.json()]
        assert "TEST_AlphaCorp" in names
        assert "TEST_BetaInc" not in names
        # without filter both present
        r2 = requests.get(f"{API}/me/companies", headers=H(candidate_token), timeout=10)
        all_names = [x["name"] for x in r2.json()]
        assert "TEST_AlphaCorp" in all_names and "TEST_BetaInc" in all_names

    def test_patch_invalid_status(self, candidate_token):
        r = requests.patch(f"{API}/me/companies/{TestMyCompanies.created_id}",
                           json={"status": "not_a_real_status"}, headers=H(candidate_token), timeout=10)
        assert r.status_code == 400

    def test_patch_valid_fields(self, candidate_token):
        body = {"status": "relance_a_faire", "note": "TEST_note_phaseC",
                "relance_date": "2026-02-01", "email": "a@b.fr", "phone": "0102",
                "website": "https://example.com"}
        r = requests.patch(f"{API}/me/companies/{TestMyCompanies.created_id}",
                           json=body, headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        # GET to verify persistence
        items = requests.get(f"{API}/me/companies", headers=H(candidate_token), timeout=10).json()
        item = next(x for x in items if x["id"] == TestMyCompanies.created_id)
        assert item["status"] == "relance_a_faire"
        assert item["note"] == "TEST_note_phaseC"
        assert item["email"] == "a@b.fr"

    def test_export_csv(self, candidate_token):
        r = requests.get(f"{API}/me/companies/export?fmt=csv", headers=H(candidate_token), timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct
        text = r.text
        assert "Nom entreprise" in text
        assert "SIRET" in text
        assert "TEST_AlphaCorp" in text

    def test_export_xlsx(self, candidate_token):
        r = requests.get(f"{API}/me/companies/export?fmt=xlsx", headers=H(candidate_token), timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "spreadsheetml" in ct or "excel" in ct
        # xlsx is a zip starting with PK
        assert r.content[:2] == b"PK"

    def test_export_pdf(self, candidate_token):
        r = requests.get(f"{API}/me/companies/export?fmt=pdf", headers=H(candidate_token), timeout=20)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower()
        assert r.content[:4] == b"%PDF"

    def test_export_invalid(self, candidate_token):
        r = requests.get(f"{API}/me/companies/export?fmt=zzz", headers=H(candidate_token), timeout=10)
        assert r.status_code == 400

    def test_delete(self, candidate_token):
        # Create disposable
        rb = requests.post(f"{API}/me/companies",
                           json={"name": "TEST_ToDelete", "siret": "TEST_DELME"},
                           headers=H(candidate_token), timeout=10)
        did = rb.json()["id"]
        r = requests.delete(f"{API}/me/companies/{did}", headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        assert r.json().get("deleted") == 1
        # confirm gone
        items = requests.get(f"{API}/me/companies", headers=H(candidate_token), timeout=10).json()
        assert not any(x["id"] == did for x in items)


# ---------- Phase C: AI spontaneous-message ----------
class TestAISpontaneous:
    def test_company_forbidden(self, company_token):
        r = requests.post(f"{API}/ai/spontaneous-message",
                          json={"company": {"name": "X"}}, headers=H(company_token), timeout=30)
        assert r.status_code == 403

    def test_generate_message(self, candidate_token):
        body = {"company": {"name": "TechNova", "city": "Lyon", "naf_code": "62.01Z"},
                "brief": "Stage 4 mois en développement web Python"}
        r = requests.post(f"{API}/ai/spontaneous-message",
                          json=body, headers=H(candidate_token), timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "message" in data
        assert isinstance(data["message"], str)
        assert len(data["message"].strip()) > 20


# ---------- Phase D: AI search ----------
class TestAISearch:
    def test_ai_search_extracts_city(self, candidate_token):
        body = {"query": "stage informatique Lyon juin"}
        r = requests.post(f"{API}/ai/search", json=body, headers=H(candidate_token), timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "criteria" in data
        crit = data["criteria"]
        # city may be 'Lyon' (case-insensitive)
        city = (crit.get("city") or "").lower()
        assert "lyon" in city

    def test_ai_search_empty_400(self, candidate_token):
        r = requests.post(f"{API}/ai/search", json={"query": ""}, headers=H(candidate_token), timeout=15)
        assert r.status_code == 400


# ---------- Phase D: search-history + history-settings ----------
class TestSearchHistory:
    def test_history_settings_enable(self, candidate_token):
        r = requests.patch(f"{API}/me/history-settings",
                           json={"history_disabled": False},
                           headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        assert r.json().get("history_disabled") is False

    def test_add_and_list_history(self, candidate_token):
        # clear first
        requests.delete(f"{API}/me/search-history", headers=H(candidate_token), timeout=10)
        body = {"search_type": "offers", "query_text": "TEST_HIST python",
                "filters": {"city": "Lyon"}, "results_count": 12, "ai_generated": True}
        r = requests.post(f"{API}/me/search-history", json=body, headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("query_text") == "TEST_HIST python"
        assert "id" in data
        TestSearchHistory.created_id = data["id"]
        # list
        lst = requests.get(f"{API}/me/search-history", headers=H(candidate_token), timeout=10).json()
        assert any(x["id"] == TestSearchHistory.created_id for x in lst)

    def test_delete_one(self, candidate_token):
        # Add a disposable item
        r = requests.post(f"{API}/me/search-history",
                          json={"search_type": "companies", "query_text": "TEST_DEL one"},
                          headers=H(candidate_token), timeout=10)
        did = r.json()["id"]
        rd = requests.delete(f"{API}/me/search-history/{did}", headers=H(candidate_token), timeout=10)
        assert rd.status_code == 200
        assert rd.json().get("deleted") == 1

    def test_history_disabled_skips(self, candidate_token):
        # disable
        r = requests.patch(f"{API}/me/history-settings",
                           json={"history_disabled": True},
                           headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        # try add -> skipped
        rp = requests.post(f"{API}/me/search-history",
                           json={"search_type": "offers", "query_text": "TEST_SKIP"},
                           headers=H(candidate_token), timeout=10)
        assert rp.status_code == 200
        assert rp.json().get("skipped") is True
        # re-enable
        requests.patch(f"{API}/me/history-settings",
                       json={"history_disabled": False},
                       headers=H(candidate_token), timeout=10)

    def test_clear_all(self, candidate_token):
        # add at least one
        requests.post(f"{API}/me/search-history",
                      json={"search_type": "offers", "query_text": "TEST_CLEAR"},
                      headers=H(candidate_token), timeout=10)
        r = requests.delete(f"{API}/me/search-history", headers=H(candidate_token), timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------- Phase E: admin api-stats ----------
class TestAdminStats:
    def test_non_admin_403(self, candidate_token):
        r = requests.get(f"{API}/admin/api-stats?days=30", headers=H(candidate_token), timeout=15)
        assert r.status_code == 403

    def test_admin_stats(self, admin_token):
        r = requests.get(f"{API}/admin/api-stats?days=30", headers=H(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["by_api", "top_queries", "top_departments", "top_naf",
                  "ai_searches", "profile_views", "obtained_count", "recent_errors"]:
            assert k in data, f"missing key {k}"
        assert isinstance(data["by_api"], list)
        assert isinstance(data["ai_searches"], int)
