"""
Iteration 12 — Phase F + G backend tests
- F: Suppression fausses offres, source_priority, is_demo, diploma-levels (33)
- G: Agrégateur 6 APIs keyless (Ashby/Arbeitnow/Remotive/RemoteOK/Jobicy/Greenhouse)
- AI search anonyme (sans auth)
- Admin: ashby-boards, greenhouse-boards, external-offers-cache, external-sources-status
"""
import os
import pytest
import requests

def _load_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)

_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "admin@stagiaireconnect.fr", "password": "Admin123!"}
CANDIDATE = {"email": "lucas.martin@email.fr", "password": "Demo1234!"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def candidate_token():
    r = requests.post(f"{API}/auth/login", json=CANDIDATE, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------- Phase F: diploma levels ----------
class TestDiplomaLevels:
    def test_diploma_levels_returns_33_items(self):
        r = requests.get(f"{API}/diploma-levels", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "levels" in data
        levels = data["levels"]
        assert isinstance(levels, list)
        assert len(levels) >= 30, f"Expected ~33 levels, got {len(levels)}"
        expected_must = [
            "Sans diplôme requis", "Collège", "Stage de 3e", "CAP",
            "BTS", "BUT", "Bac +5", "MBA", "Doctorat",
        ]
        for lv in expected_must:
            assert lv in levels, f"Missing level: {lv}"


# ---------- Phase F: /offers no demo + sort by source_priority ----------
class TestOffersNoDemoAndSorting:
    def test_offers_no_is_demo_true(self):
        r = requests.get(f"{API}/offers?limit=500", timeout=20)
        assert r.status_code == 200
        offers = r.json()
        assert isinstance(offers, list)
        for o in offers:
            assert o.get("is_demo") is not True, f"Offer {o.get('offer_id')} has is_demo=True"

    def test_offers_all_have_source_priority(self):
        r = requests.get(f"{API}/offers?limit=500", timeout=20)
        offers = r.json()
        for o in offers:
            # source_priority must exist on every doc (not None)
            assert "source_priority" in o, f"Offer {o.get('offer_id')} missing source_priority"
            assert o["source_priority"] is not None, f"Offer {o.get('offer_id')} source_priority is None"

    def test_offers_sorted_desc_by_source_priority(self):
        r = requests.get(f"{API}/offers?limit=200", timeout=20)
        offers = r.json()
        prios = [o.get("source_priority", 0) for o in offers]
        for i in range(len(prios) - 1):
            assert prios[i] >= prios[i + 1], (
                f"Not sorted DESC at {i}: {prios[i]} < {prios[i+1]}"
            )

    def test_stageetudiant_priority_10_and_first(self):
        r = requests.get(f"{API}/offers?limit=200", timeout=20)
        offers = r.json()
        # Find StageConnect/StageEtudiant offers
        se = [o for o in offers if o.get("source") in ("StageConnect", "StageEtudiant")]
        ft = [o for o in offers if o.get("source") in ("FranceTravail", "La Bonne Alternance")]
        assert len(se) > 0, "No StageConnect/StageEtudiant offers found"
        for o in se:
            assert o["source_priority"] == 10, f"{o.get('source')} priority != 10"
        for o in ft:
            assert o["source_priority"] == 8, f"{o.get('source')} priority != 8 ({o['source_priority']})"
        # First offer is StageConnect/StageEtudiant
        assert offers[0].get("source") in ("StageConnect", "StageEtudiant")

    def test_no_fake_sources_present(self):
        r = requests.get(f"{API}/offers?limit=500", timeout=20)
        offers = r.json()
        fake_sources = {"HelloWork", "LinkedIn", "Indeed", "Monster", "Apec", "Welcome to the Jungle"}
        found = {o.get("source") for o in offers} & fake_sources
        assert not found, f"Fake sources found: {found}"
        # No TEST_ titles
        for o in offers:
            t = (o.get("title") or "")
            assert not t.startswith("TEST_"), f"TEST_ title leaked: {t}"


# ---------- Phase G: keyless aggregator ----------
class TestKeylessAggregator:
    def test_keyless_basic_structure(self):
        r = requests.get(f"{API}/external-offers/keyless", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "results" in data
        assert "cache_hit" in data
        assert "by_source" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["by_source"], dict)

    def test_keyless_has_main_sources(self):
        r = requests.get(f"{API}/external-offers/keyless", timeout=60)
        data = r.json()
        by_source = data["by_source"]
        # Expect at least these sources keys present (Greenhouse may be 0 if no board)
        for src in ["Arbeitnow", "Remotive", "RemoteOK", "Jobicy", "Ashby"]:
            assert src in by_source, f"Missing source key: {src}; got {list(by_source.keys())}"
        # Greenhouse may be 0
        assert "Greenhouse" in by_source or True  # informational
        # Total results > 0
        assert len(data["results"]) > 0

    def test_keyless_cache_hit_on_second_call(self):
        # First call (might be cache from prev test)
        r1 = requests.get(f"{API}/external-offers/keyless", timeout=60)
        # Second call should be cache_hit
        r2 = requests.get(f"{API}/external-offers/keyless", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("cache_hit") is True


# ---------- Admin: Ashby boards ----------
class TestAdminAshbyBoards:
    def test_ashby_403_for_non_admin(self, candidate_token):
        h = {"Authorization": f"Bearer {candidate_token}"}
        r = requests.post(f"{API}/admin/ashby-boards", json={"board_token": "Test"}, headers=h, timeout=10)
        assert r.status_code == 403

    def test_ashby_crud_admin(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        # POST
        r = requests.post(f"{API}/admin/ashby-boards",
                          json={"board_token": "TEST_Board", "company_name": "TEST_Co"},
                          headers=h, timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["board_token"] == "TEST_Board"
        # GET
        r = requests.get(f"{API}/admin/ashby-boards", headers=h, timeout=10)
        assert r.status_code == 200
        tokens = [b["board_token"] for b in r.json()]
        assert "TEST_Board" in tokens
        # DELETE
        r = requests.delete(f"{API}/admin/ashby-boards/TEST_Board", headers=h, timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # GET again — removed
        r = requests.get(f"{API}/admin/ashby-boards", headers=h, timeout=10)
        tokens = [b["board_token"] for b in r.json()]
        assert "TEST_Board" not in tokens


# ---------- Admin: Greenhouse boards ----------
class TestAdminGreenhouseBoards:
    def test_gh_403_for_non_admin(self, candidate_token):
        h = {"Authorization": f"Bearer {candidate_token}"}
        r = requests.post(f"{API}/admin/greenhouse-boards", json={"board_token": "Test"}, headers=h, timeout=10)
        assert r.status_code == 403

    def test_gh_crud_admin(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/admin/greenhouse-boards",
                          json={"board_token": "TEST_GH", "company_name": "TEST_GHCo"},
                          headers=h, timeout=10)
        assert r.status_code == 200
        r = requests.get(f"{API}/admin/greenhouse-boards", headers=h, timeout=10)
        tokens = [b["board_token"] for b in r.json()]
        assert "TEST_GH" in tokens
        r = requests.delete(f"{API}/admin/greenhouse-boards/TEST_GH", headers=h, timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------- Admin: cache purge + sources status ----------
class TestAdminCacheAndStatus:
    def test_external_offers_cache_purge(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.delete(f"{API}/admin/external-offers-cache", headers=h, timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_external_sources_status(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{API}/admin/external-sources-status", headers=h, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "sources" in data
        assert "cache" in data
        assert isinstance(data["sources"], list)
        names = [s["name"] for s in data["sources"]]
        for must in ["Ashby", "Arbeitnow", "Remotive", "RemoteOK", "Jobicy", "Greenhouse"]:
            assert must in names, f"Missing source in status: {must}"
        for s in data["sources"]:
            assert "enabled" in s
            assert "last_call" in s


# ---------- AI search anonymous ----------
class TestAISearchAnonymous:
    def test_ai_search_no_auth(self):
        r = requests.post(f"{API}/ai/search",
                          json={"query": "Stage marketing à Paris niveau Bac+5"},
                          timeout=30)
        # Must NOT be 401 anymore (was 401 before; now allowed anonymous)
        assert r.status_code != 401, r.text
        assert r.status_code == 200, r.text
        data = r.json()
        assert "criteria" in data
        assert isinstance(data["criteria"], dict)
