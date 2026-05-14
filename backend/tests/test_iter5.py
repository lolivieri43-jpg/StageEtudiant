"""Iteration 5 backend tests:
- Avatar/banner upload (Pillow compression) + GET /api/files/{id}
- DELETE avatar/banner
- /profile-v2 cascading company name rename
- /candidates/featured (premium first + is_premium flag)
- /admin/grant-premium/{user_id}?days=30
- /admin/refresh-external?source=FranceTravail (simulation fallback)
- /admin/external-connectors (FranceTravail enabled=False, status=simulation_only)
- Mongo indexes ensured on startup (smoke-checked via supervisor log)
"""
import io
import os
import uuid
import pytest
import requests
from PIL import Image

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE}/api"


def H(t):
    return {"Authorization": f"Bearer {t}"}


# ----- Auth fixtures -----
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@stagiaireconnect.fr", "password": "Admin123!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def candidate_token():
    r = requests.post(f"{API}/auth/login", json={"email": "lucas.martin@email.fr", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def company_token():
    r = requests.post(f"{API}/auth/login", json={"email": "hr@technova.fr", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def candidate_me(candidate_token):
    return requests.get(f"{API}/auth/me", headers=H(candidate_token)).json()


@pytest.fixture(scope="session")
def company_me(company_token):
    return requests.get(f"{API}/auth/me", headers=H(company_token)).json()


def _make_png_bytes(size=(800, 800), color=(120, 200, 50)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(size=(2000, 1200)):
    buf = io.BytesIO()
    Image.new("RGB", size, (255, 100, 50)).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ===== AVATAR =====
def test_avatar_upload_compresses_and_returns_url(candidate_token):
    png = _make_png_bytes((1200, 1200))
    r = requests.post(f"{API}/me/avatar", headers=H(candidate_token),
                      files={"file": ("test_avatar.png", png, "image/png")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data and "file_id" in data
    assert data["url"].startswith("/api/files/")
    # GET serves compressed image (note: served via authenticated endpoint)
    file_id = data["file_id"]
    g = requests.get(f"{BASE}{data['url']}", headers=H(candidate_token))
    assert g.status_code == 200, f"GET /api/files/{file_id} returned {g.status_code} — avatars must be retrievable"
    assert g.headers.get("content-type", "").startswith("image/")
    # Ensure compression happened (output smaller than original 1200x1200 PNG)
    assert len(g.content) < len(png)
    # Verify thumbnail <= 512x512
    img = Image.open(io.BytesIO(g.content))
    assert img.size[0] <= 512 and img.size[1] <= 512
    # Verify profile updated (candidate role -> avatar key)
    me = requests.get(f"{API}/auth/me", headers=H(candidate_token)).json()
    assert me.get("profile", {}).get("avatar") == data["url"]


def test_avatar_publicly_accessible_for_img_tags(candidate_token):
    """Critical: <img src=/api/files/...> can't send Bearer auth.
    Avatars (kind='avatar') and banners must be reachable without auth headers,
    otherwise the UI cannot display them. Currently fails because the file route
    enforces ownership for files with no document/photo reference."""
    png = _make_png_bytes((400, 400))
    up = requests.post(f"{API}/me/avatar", headers=H(candidate_token),
                       files={"file": ("a.png", png, "image/png")}).json()
    # Anonymous request — simulating a browser <img> tag
    g = requests.get(f"{BASE}{up['url']}")
    assert g.status_code == 200, (
        f"Avatar must be publicly accessible for <img> tags; got {g.status_code}. "
        "This is a critical UI integration bug: the frontend cannot render avatars."
    )



    r = requests.post(f"{API}/me/avatar", headers=H(candidate_token),
                      files={"file": ("doc.txt", b"hello world not an image", "text/plain")})
    assert r.status_code == 400, r.text


def test_avatar_upload_requires_auth():
    png = _make_png_bytes((400, 400))
    r = requests.post(f"{API}/me/avatar", files={"file": ("a.png", png, "image/png")})
    assert r.status_code in (401, 403)


def test_company_avatar_sets_logo_key(company_token):
    png = _make_png_bytes((600, 600), color=(30, 30, 200))
    r = requests.post(f"{API}/me/avatar", headers=H(company_token),
                      files={"file": ("logo.png", png, "image/png")})
    assert r.status_code == 200, r.text
    me = requests.get(f"{API}/auth/me", headers=H(company_token)).json()
    # For company role, the avatar must be stored under profile.logo
    assert me.get("profile", {}).get("logo") == r.json()["url"]


def test_avatar_delete_removes_profile_avatar(candidate_token):
    # Ensure avatar is set
    png = _make_png_bytes((400, 400))
    requests.post(f"{API}/me/avatar", headers=H(candidate_token),
                  files={"file": ("a.png", png, "image/png")})
    r = requests.delete(f"{API}/me/avatar", headers=H(candidate_token))
    assert r.status_code == 200, r.text
    me = requests.get(f"{API}/auth/me", headers=H(candidate_token)).json()
    assert "avatar" not in me.get("profile", {})


# ===== BANNER =====
def test_banner_upload_compresses(candidate_token):
    jpg = _make_jpeg_bytes((2400, 1000))
    r = requests.post(f"{API}/me/banner", headers=H(candidate_token),
                      files={"file": ("banner.jpg", jpg, "image/jpeg")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data and "file_id" in data
    g = requests.get(f"{BASE}{data['url']}", headers=H(candidate_token))
    assert g.status_code == 200
    img = Image.open(io.BytesIO(g.content))
    assert img.size[0] <= 1600 and img.size[1] <= 600
    me = requests.get(f"{API}/auth/me", headers=H(candidate_token)).json()
    assert me.get("profile", {}).get("banner") == data["url"]


def test_banner_delete(candidate_token):
    jpg = _make_jpeg_bytes((1800, 700))
    requests.post(f"{API}/me/banner", headers=H(candidate_token),
                  files={"file": ("b.jpg", jpg, "image/jpeg")})
    r = requests.delete(f"{API}/me/banner", headers=H(candidate_token))
    assert r.status_code == 200, r.text
    me = requests.get(f"{API}/auth/me", headers=H(candidate_token)).json()
    assert "banner" not in me.get("profile", {})


# ===== /profile-v2 cascade =====
def test_profile_v2_company_name_cascade(company_token, company_me):
    company_id = company_me["user_id"]
    original_name = company_me.get("profile", {}).get("company_name") or company_me.get("name")
    # Create a post + offer first to have records that can be cascaded
    requests.post(f"{API}/posts", headers=H(company_token),
                  json={"content": "TEST_iter5 cascade post"})
    offer_r = requests.post(f"{API}/offers", headers=H(company_token), json={
        "title": "TEST_iter5 cascade offer", "contract_type": "stage", "domain": "Test",
        "city": "Paris", "region": "Île-de-France", "remote": False, "duration": "3 mois",
        "level": "Bac+3", "skills": [], "description": "x", "profile": "", "benefits": "",
    })
    new_name = f"TestCo_{uuid.uuid4().hex[:6]}"
    r = requests.put(f"{API}/profile-v2", headers=H(company_token),
                     json={"company_name": new_name})
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated.get("name") == new_name  # root name updated
    assert updated.get("profile", {}).get("company_name") == new_name

    # Verify cascade on offers
    offers = requests.get(f"{API}/offers", params={"company_id": company_id, "limit": 5}).json()
    if isinstance(offers, dict): offers = offers.get("offers", offers)
    if offers:
        for o in offers:
            if o.get("company_id") == company_id:
                assert o.get("company_name") == new_name, f"Offer not cascaded: {o.get('offer_id')}"
                break

    # Restore original name to avoid polluting demo data
    if original_name:
        requests.put(f"{API}/profile-v2", headers=H(company_token),
                     json={"company_name": original_name})


def test_profile_v2_candidate_simple_update(candidate_token):
    r = requests.put(f"{API}/profile-v2", headers=H(candidate_token),
                     json={"city": "Lyon"})
    assert r.status_code == 200, r.text
    assert r.json().get("profile", {}).get("city") == "Lyon"


# ===== /candidates/featured =====
def test_candidates_featured_returns_premium_first(admin_token, candidate_me):
    # Make sure at least one candidate is premium so we can verify ordering
    requests.post(f"{API}/admin/grant-premium/{candidate_me['user_id']}",
                  headers=H(admin_token), params={"days": 30})
    r = requests.get(f"{API}/candidates/featured", params={"limit": 8})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Every entry must have is_premium boolean
    for c in data:
        assert "is_premium" in c
        assert isinstance(c["is_premium"], bool)
    # Premium entries must come before non-premium (premium-first ordering)
    has_premium = any(c["is_premium"] for c in data)
    if has_premium:
        last_premium_idx = max(i for i, c in enumerate(data) if c["is_premium"])
        first_regular_idx = next((i for i, c in enumerate(data) if not c["is_premium"]), None)
        if first_regular_idx is not None:
            assert last_premium_idx < first_regular_idx, "Premium must appear before regular"


# ===== /admin/grant-premium =====
def test_grant_premium_requires_admin(candidate_token, candidate_me):
    r = requests.post(f"{API}/admin/grant-premium/{candidate_me['user_id']}",
                      headers=H(candidate_token), params={"days": 30})
    assert r.status_code == 403


def test_grant_premium_sets_fields(admin_token, candidate_me):
    r = requests.post(f"{API}/admin/grant-premium/{candidate_me['user_id']}",
                      headers=H(admin_token), params={"days": 30})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    # Verify on /auth/me when logging in as that candidate
    login = requests.post(f"{API}/auth/login",
                         json={"email": "lucas.martin@email.fr", "password": "Demo1234!"}).json()
    me = requests.get(f"{API}/auth/me", headers=H(login["token"])).json()
    p = me.get("profile", {})
    assert p.get("is_premium") is True
    assert p.get("premium_status") == "active"
    assert p.get("premium_start_date") and p.get("premium_end_date")


def test_grant_premium_404_for_unknown_user(admin_token):
    r = requests.post(f"{API}/admin/grant-premium/non_existent_user_id",
                      headers=H(admin_token), params={"days": 30})
    assert r.status_code == 404


# ===== /admin/refresh-external (FranceTravail simulation fallback) =====
def test_refresh_external_france_travail_simulation(admin_token):
    r = requests.post(f"{API}/admin/refresh-external",
                      headers=H(admin_token),
                      params={"source": "FranceTravail", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("source") == "FranceTravail"
    assert "fetched" in data and "inserted" in data
    assert data["fetched"] >= 0


def test_refresh_external_hellowork(admin_token):
    r = requests.post(f"{API}/admin/refresh-external",
                      headers=H(admin_token),
                      params={"source": "HelloWork", "limit": 3})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_refresh_external_requires_admin(candidate_token):
    r = requests.post(f"{API}/admin/refresh-external", headers=H(candidate_token),
                      params={"source": "FranceTravail", "limit": 2})
    assert r.status_code == 403


# ===== /admin/external-connectors =====
def test_external_connectors_list(admin_token):
    r = requests.get(f"{API}/admin/external-connectors", headers=H(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "connectors" in data
    names = {c["name"]: c for c in data["connectors"]}
    assert "FranceTravail" in names
    ft = names["FranceTravail"]
    # No credentials configured in env -> enabled False, status simulation_only
    assert ft["enabled"] is False
    assert ft["status"] == "simulation_only"


# ===== Mongo indexes log line =====
def test_mongo_indexes_log_present():
    """Smoke-check that 'Mongo indexes ensured' appears in supervisor backend logs."""
    import subprocess
    out = subprocess.run(
        ["bash", "-lc", "grep -l 'Mongo indexes ensured' /var/log/supervisor/backend.*.log || true"],
        capture_output=True, text=True
    )
    assert out.stdout.strip(), f"'Mongo indexes ensured' not found in backend logs: {out.stderr}"
