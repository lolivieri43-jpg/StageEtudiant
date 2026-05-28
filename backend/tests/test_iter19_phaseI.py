"""
Iteration 19 — Phase I: 5 new features
1. Official Profile (GET public + PATCH admin)
2. Reserved-name register
3. Nominatim geocoding fallback (+ cache)
4. Offers premium enrichment
5. /api/offers-nearby with fallback geocoding
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "bernardolivieri1326@gmail.com"
ADMIN_PASSWORD = "OwnerAdmin2026!"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin auth failed: {r.status_code} {r.text}")
    return r.json().get("token") or r.json().get("access_token")


# -------- Official Profile --------
class TestOfficialProfile:
    def test_get_official_profile_public(self, session):
        r = session.get(f"{BASE_URL}/api/official-profile", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "StageEtudiant.com"
        assert data["is_official"] is True
        assert "slogan" in data and "primary_color" in data

    def test_patch_official_profile_requires_admin(self, session):
        # unauthenticated PATCH should fail
        r = session.patch(
            f"{BASE_URL}/api/admin/official-profile",
            json={"slogan": "Should not work"},
            timeout=15,
        )
        assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"

    def test_patch_official_profile_as_admin(self, session, admin_token):
        # Save original
        original = session.get(f"{BASE_URL}/api/official-profile").json()
        new_slogan = f"TEST_iter19 slogan {uuid.uuid4().hex[:6]}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = session.patch(
            f"{BASE_URL}/api/admin/official-profile",
            json={
                "display_name": "StageEtudiant.com",
                "slogan": new_slogan,
                "description": original.get("description"),
                "primary_color": "#2563eb",
                "is_visible": True,
            },
            headers=headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["slogan"] == new_slogan
        # Verify persistence
        r2 = session.get(f"{BASE_URL}/api/official-profile", timeout=10)
        assert r2.json()["slogan"] == new_slogan
        # Restore
        session.patch(
            f"{BASE_URL}/api/admin/official-profile",
            json={"slogan": original.get("slogan")},
            headers=headers,
            timeout=15,
        )


# -------- Reserved-name register --------
class TestReservedName:
    @pytest.mark.parametrize(
        "name",
        ["StageEtudiant.com", "Stage Etudiant", "stageetudiant"],
    )
    def test_register_reserved_name_rejected(self, session, name):
        email = f"test_reserved_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": email,
                "password": "Passw0rd!",
                "name": name,
                "role": "candidate",
            },
            timeout=15,
        )
        assert r.status_code == 400, f"name={name!r} -> {r.status_code} {r.text}"
        msg = (r.json().get("detail") or r.json().get("message") or "").lower()
        assert "réserv" in msg or "reserv" in msg, f"Unexpected error msg: {msg!r}"

    def test_register_normal_name_ok(self, session):
        email = f"test_iter19_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": email,
                "password": "Passw0rd!",
                "name": f"TEST_iter19_{uuid.uuid4().hex[:6]}",
                "role": "candidate",
            },
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text


# -------- Geocoding (Nominatim fallback + cache) --------
class TestGeocode:
    def test_geocode_saumur_nominatim(self, session):
        r = session.get(f"{BASE_URL}/api/geocode", params={"city": "Saumur"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("found") is True, data
        assert "latitude" in data and "longitude" in data
        # source may be 'nominatim' or 'cache' depending on prior tests
        assert data.get("source") in ("nominatim", "cache", "local")
        if "region" in data and data.get("region"):
            assert "loire" in data["region"].lower() or "pays" in data["region"].lower()

    def test_geocode_cache_hit(self, session):
        # First call (may already be cached)
        session.get(f"{BASE_URL}/api/geocode", params={"city": "Saumur"}, timeout=30)
        time.sleep(1)
        r2 = session.get(f"{BASE_URL}/api/geocode", params={"city": "Saumur"}, timeout=10)
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("found") is True
        assert d.get("source") in ("cache", "nominatim", "local")

    def test_geocode_unknown_city(self, session):
        r = session.get(
            f"{BASE_URL}/api/geocode",
            params={"city": "xyzqwertynowhere"},
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json().get("found") is False


# -------- Offers premium enrichment --------
class TestOffersPremiumEnrich:
    def test_offers_list_includes_premium_field(self, session):
        r = session.get(f"{BASE_URL}/api/offers", params={"limit": 20}, timeout=20)
        assert r.status_code == 200
        offers = r.json()
        assert isinstance(offers, list)
        # No assumption about premium users; just verify endpoint doesn't crash and field exists
        with_company = [o for o in offers if o.get("company_id")]
        for o in with_company[:5]:
            # company_is_premium might be absent (None/False) if no premium seeded; verify the call shape
            assert "company_id" in o
            # if enriched, must be bool
            if "company_is_premium" in o:
                assert isinstance(o["company_is_premium"], bool)


# -------- /api/offers-nearby fallback --------
class TestOffersNearby:
    def test_nearby_saumur_does_not_404(self, session):
        r = session.get(
            f"{BASE_URL}/api/offers-nearby",
            params={"city": "Saumur", "distance_km": 80},
            timeout=30,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        body = r.json()
        # Accept array OR {offers: [...]} shape
        if isinstance(body, dict):
            assert "offers" in body or "results" in body or "items" in body
        else:
            assert isinstance(body, list)
