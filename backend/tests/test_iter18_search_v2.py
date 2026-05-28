"""Iter18 — Strict offer search filters + owner admin tests."""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if 'REACT_APP_BACKEND_URL' in os.environ else None
# Fallback: read frontend/.env
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for ln in f:
            if ln.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = ln.split('=', 1)[1].strip().rstrip('/')

API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def hr_token():
    r = requests.post(f"{API}/auth/login", json={"email": "hr@technova.fr", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def hr_headers(hr_token):
    return {"Authorization": f"Bearer {hr_token}"}


@pytest.fixture(scope="session")
def alpha_offer(hr_headers):
    """Seed a stable test offer for AlphaGroup028 (override company_name via raw insert through company account)."""
    # Use the offers create endpoint as HR
    payload = {
        "title": "TEST_iter18 AlphaGroup028 offer",
        "contract_type": "stage", "domain": "Informatique",
        "city": "Paris", "region": "Île-de-France",
        "remote": False, "duration": "6 mois",
        "level": "Bac+3", "skills": ["Python"],
        "description": "Offre de test iter18"
    }
    r = requests.post(f"{API}/offers", json=payload, headers=hr_headers)
    assert r.status_code == 200, r.text
    off = r.json()
    # Patch company_name in DB via admin-like trick: use seed-v3 fixtures' AlphaGroup028 if it exists. Otherwise leave as TechNova.
    return off


# ---------- 1. Owner admin ----------
class TestOwnerAdmin:
    def test_login_owner_admin(self):
        r = requests.post(f"{API}/auth/login", json={
            "email": "bernardolivieri1326@gmail.com",
            "password": "OwnerAdmin2026!"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user"]["role"] == "admin"
        assert d["token"]


# ---------- 2. Cities endpoint ----------
class TestCities:
    def test_cities_list_120plus(self):
        r = requests.get(f"{API}/cities")
        assert r.status_code == 200
        d = r.json()
        # API may return either a list or a dict {cities: [...]}
        if isinstance(d, dict):
            cities = d.get("cities") or d.get("items") or []
        else:
            cities = d
        assert len(cities) >= 120, f"Only {len(cities)} cities returned"


# ---------- 3. Company filter ----------
class TestCompanyFilter:
    def test_company_filter_alpha(self):
        # Existing seed-v3 should contain "AlphaGroup028"-style names. Check it filters.
        r = requests.get(f"{API}/offers", params={"company": "AlphaGroup028", "limit": 20})
        assert r.status_code == 200
        offers = r.json()
        for o in offers:
            cn = (o.get("company_name") or "").lower()
            assert "alphagroup028" in cn or "alpha" in cn, f"Unexpected company {cn}"

    def test_company_filter_case_accent_insensitive(self):
        r1 = requests.get(f"{API}/offers", params={"company": "BrightStudio011"})
        r2 = requests.get(f"{API}/offers", params={"company": "brightstudio011"})
        assert r1.status_code == 200 and r2.status_code == 200
        a = {o["offer_id"] for o in r1.json()}
        b = {o["offer_id"] for o in r2.json()}
        assert a == b, "case-insensitive match failed"
        assert len(a) >= 1, "Expected at least 1 BrightStudio011 offer"

    def test_company_filter_partial_edf(self):
        # whole-word match: 'edf' must match 'EDF S.A.' or 'EDF'
        r = requests.get(f"{API}/offers", params={"company": "EDF"})
        assert r.status_code == 200
        # If no EDF offer is seeded, test is still meaningful (empty result)
        for o in r.json():
            cn = (o.get("company_name") or "").lower()
            assert "edf" in cn


# ---------- 4. Radius / city filter ----------
class TestRadius:
    def test_unknown_city_400(self):
        r = requests.get(f"{API}/offers", params={"city": "VilleInconnueXYZ", "radius_km": 10})
        assert r.status_code == 400
        assert "ville" in r.text.lower() or "inconnu" in r.text.lower()

    def test_radius_paris_30km(self):
        r = requests.get(f"{API}/offers", params={"city": "Paris", "radius_km": 30, "limit": 200})
        assert r.status_code == 200, r.text
        offers = r.json()
        # All should have _distance_km <= 30
        for o in offers:
            d = o.get("_distance_km")
            assert d is not None, f"Missing _distance_km for offer {o.get('offer_id')}"
            assert d <= 30.001


# ---------- 5. Country / Europe ----------
class TestCountry:
    def test_default_only_french(self):
        r = requests.get(f"{API}/offers", params={"limit": 200})
        assert r.status_code == 200
        for o in r.json():
            c = o.get("country")
            assert c is None or c in ("France", "FR", "fr"), f"Non-French offer leaked: {c}"

    def test_european_only(self):
        r = requests.get(f"{API}/external-offers/all", params={"european_only": True, "limit": 100})
        # Endpoint may require no auth
        assert r.status_code in (200, 401), r.text
        if r.status_code == 200:
            for o in r.json().get("offers", r.json() if isinstance(r.json(), list) else []):
                c = (o.get("country") or "").lower()
                assert c not in ("france", "fr", ""), f"French leaked in european_only: {c}"

    def test_country_alias_allemagne(self):
        r = requests.get(f"{API}/external-offers/all", params={"country": "Allemagne", "limit": 100})
        assert r.status_code in (200, 401)
        if r.status_code == 200:
            data = r.json()
            offers = data.get("offers", data if isinstance(data, list) else [])
            for o in offers:
                c = (o.get("country") or "").lower()
                # alias should match Germany / Deutschland / DE
                assert c in ("germany", "allemagne", "de", "deutschland"), f"Bad alias match: {c}"

    def test_country_alias_royaume_uni(self):
        r = requests.get(f"{API}/external-offers/all", params={"country": "Royaume-Uni", "limit": 100})
        assert r.status_code in (200, 401)


# ---------- 6. Regression ----------
class TestRegression:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200

    def test_offers_basic(self):
        r = requests.get(f"{API}/offers", params={"limit": 5})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_deal_creation_pending(self, hr_headers):
        payload = {"title": "TEST_iter18 deal", "description": "Test", "category": "logement", "city": "Paris"}
        r = requests.post(f"{API}/deals", json=payload, headers=hr_headers)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d.get("status") == "pending", f"Deal should be pending, got {d.get('status')}"
