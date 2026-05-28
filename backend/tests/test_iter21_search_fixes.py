"""Iteration 21 — tests for the two bug-fixes:
   BUG #1: GET /api/offers?company=<term> uses substring (not whole-word) match for terms of 3+ chars
   BUG #2: GET /api/search/students?q=Lucas works for admin users too
   Plus iteration_20 regression smoke checks.
"""
import os
import pathlib

import pytest
import requests

# Resolve REACT_APP_BACKEND_URL from env or frontend/.env (safe pattern)
def _resolve_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    env_path = pathlib.Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _resolve_base_url()
ADMIN_EMAIL = "bernardolivieri1326@gmail.com"
ADMIN_PWD = "OwnerAdmin2026!"
COMPANY_EMAIL = "hr@technova.fr"
COMPANY_PWD = "Demo1234!"


# ----------- Fixtures -----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(session, email, pwd):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token(session):
    return _login(session, ADMIN_EMAIL, ADMIN_PWD)


@pytest.fixture(scope="module")
def company_token(session):
    return _login(session, COMPANY_EMAIL, COMPANY_PWD)


# ----------- BUG #1: offers company substring match -----------
class TestOffersCompanySubstring:
    def test_beta_returns_at_least_3_offers(self, session):
        r = session.get(f"{BASE_URL}/api/offers", params={"company": "Beta"})
        assert r.status_code == 200
        offers = r.json()
        names = [o.get("company_name") or o.get("company") for o in offers]
        # Expect BetaSystems081 x2 + BetaTech065 (>=3)
        assert len(offers) >= 3, f"Expected >=3 offers for 'Beta', got {len(offers)}: {names}"
        # All matched offers should contain 'beta' (case-insensitive)
        for n in names:
            assert n and "beta" in (n or "").lower(), f"Unexpected company in result: {n}"

    def test_bright_returns_at_least_1(self, session):
        r = session.get(f"{BASE_URL}/api/offers", params={"company": "Bright"})
        assert r.status_code == 200
        offers = r.json()
        assert len(offers) >= 1
        for o in offers:
            assert "bright" in (o.get("company_name") or "").lower()

    def test_exact_betasystems081_still_matches(self, session):
        r = session.get(f"{BASE_URL}/api/offers", params={"company": "BetaSystems081"})
        assert r.status_code == 200
        offers = r.json()
        # Expect exactly the 2 offers from BetaSystems081
        assert len(offers) >= 2
        for o in offers:
            assert (o.get("company_name") or "").lower() == "betasystems081"

    def test_short_term_a_returns_zero(self, session):
        """Very short term must NOT match every offer (whole-word fallback)."""
        r = session.get(f"{BASE_URL}/api/offers", params={"company": "a"})
        assert r.status_code == 200
        offers = r.json()
        # 'a' is too short → whole-word match → should be 0 (no company named exactly 'a')
        assert len(offers) == 0, f"Expected 0 offers for short 'a', got {len(offers)}"

    def test_nonexistent_company_returns_zero(self, session):
        """Sofratom doesn't exist in internal data."""
        r = session.get(f"{BASE_URL}/api/offers", params={"company": "Sofratom"})
        assert r.status_code == 200
        offers = r.json()
        assert len(offers) == 0, f"Expected 0 offers for 'Sofratom', got {len(offers)}"

    def test_external_offers_sofratom_zero(self, session):
        r = session.get(f"{BASE_URL}/api/external-offers/all", params={"company": "Sofratom"})
        assert r.status_code == 200
        data = r.json()
        # Endpoint may return list or {items: [...]}
        items = data if isinstance(data, list) else data.get("items", data.get("results", []))
        assert len(items) == 0, f"Expected 0 external offers for 'Sofratom', got {len(items)}"

    def test_francetravail_sofratom_zero(self, session):
        r = session.get(f"{BASE_URL}/api/francetravail/search", params={"q": "Sofratom"})
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("results", []))
        assert len(items) == 0, f"Expected 0 FT offers for 'Sofratom', got {len(items)}"


# ----------- BUG #2: admin can search students -----------
class TestAdminSearchStudents:
    def test_admin_search_lucas(self, session, admin_token):
        r = session.get(
            f"{BASE_URL}/api/search/students",
            params={"q": "Lucas"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        results = r.json()
        names = [s.get("name") for s in results]
        assert any("Lucas Martin" in (n or "") for n in names), f"Lucas Martin not found in {names}"

    def test_company_search_lucas_regression(self, session, company_token):
        r = session.get(
            f"{BASE_URL}/api/search/students",
            params={"q": "Martin"},
            headers={"Authorization": f"Bearer {company_token}"},
        )
        assert r.status_code == 200
        results = r.json()
        names = [s.get("name") for s in results]
        assert any("Lucas Martin" in (n or "") for n in names), f"Lucas Martin not found in {names}"


# ----------- Iteration 20 regression -----------
class TestIter20Regression:
    def test_auth_me_admin(self, session, admin_token):
        r = session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"

    def test_admin_stats(self, session, admin_token):
        r = session.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "users" in data or "total_users" in data or len(data) > 0

    def test_offers_regions(self, session):
        r = session.get(f"{BASE_URL}/api/offers/regions")
        assert r.status_code == 200
        data = r.json()
        # Endpoint returns {by_region: [...]} (or list in legacy versions)
        regions = data.get("by_region", data) if isinstance(data, dict) else data
        assert isinstance(regions, list)
        assert len(regions) >= 10

    def test_users_public_profile(self, session):
        # Fetch any offer → derive a user_id → call /users/{id}
        r = session.get(f"{BASE_URL}/api/offers")
        assert r.status_code == 200
        offers = r.json()
        # Find an offer with a posted_by/company_user_id
        uid = None
        for o in offers:
            uid = o.get("posted_by") or o.get("company_user_id") or o.get("user_id")
            if uid:
                break
        if not uid:
            pytest.skip("No user_id derivable from offers; skipping public profile check")
        r2 = session.get(f"{BASE_URL}/api/users/{uid}")
        assert r2.status_code == 200, f"{r2.status_code} {r2.text}"
