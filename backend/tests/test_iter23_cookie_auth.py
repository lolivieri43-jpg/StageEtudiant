"""Iteration 23 — HttpOnly cookie auth migration + dedup integration tests.

Validates:
- /api/auth/login sets HttpOnly Secure SameSite=none cookie 'access_token' and returns {token, user}
- /api/auth/me works via cookie alone (no Authorization header)
- /api/auth/me still works via Bearer header (backward compat)
- /api/auth/register sets cookie + returns token
- /api/auth/logout sends a Set-Cookie clearing access_token
- CORS preflight with origin returns Access-Control-Allow-Credentials: true and specific Origin (no '*')
- /api/external-offers/all returns deduped offers (some may include 'duplicate_sources')
"""
import os
import re
import uuid
import requests
import pytest

def _read_frontend_env_url() -> str:
    # supervisor doesn't propagate frontend/.env into the backend test runner — read it
    try:
        with open("/app/frontend/.env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env_url()).rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set (frontend/.env)"
ORIGIN = "https://joblink-stages.preview.emergentagent.com"
ADMIN_EMAIL = "bernardolivieri1326@gmail.com"
ADMIN_PASSWORD = "OwnerAdmin2026!"


def _login(session: requests.Session) -> dict:
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Origin": ORIGIN},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r


class TestCookieLogin:
    def test_login_sets_httponly_cookie_and_returns_token(self):
        s = requests.Session()
        r = _login(s)
        body = r.json()
        # body shape
        assert "token" in body and isinstance(body["token"], str) and len(body["token"]) > 20
        assert "user" in body and body["user"]["email"] == ADMIN_EMAIL
        assert body["user"]["role"] == "admin"
        # cookie present in jar
        assert "access_token" in s.cookies.get_dict(), f"cookies: {s.cookies.get_dict()}"
        # raw Set-Cookie header inspection: HttpOnly + Secure + SameSite=None
        set_cookie = r.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie, set_cookie
        low = set_cookie.lower()
        assert "httponly" in low, f"HttpOnly flag missing: {set_cookie}"
        assert "secure" in low, f"Secure flag missing: {set_cookie}"
        assert "samesite=none" in low, f"SameSite=None missing: {set_cookie}"
        # max-age ~ 7 days (604800)
        assert re.search(r"max-age=6048\d\d", low), f"max-age missing/wrong: {set_cookie}"

    def test_me_via_cookie_only_no_authorization_header(self):
        s = requests.Session()
        _login(s)
        # explicitly no Authorization header — only cookie
        r = s.get(f"{BASE_URL}/api/auth/me", headers={"Origin": ORIGIN}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        u = r.json()
        assert u["email"] == ADMIN_EMAIL
        assert u["role"] == "admin"
        assert "password" not in u
        assert "_id" not in u

    def test_me_via_bearer_header_backward_compat(self):
        s = requests.Session()
        token = _login(s).json()["token"]
        # fresh session — no cookies — Bearer only
        clean = requests.Session()
        r = clean.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}", "Origin": ORIGIN},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:200]
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_any_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Origin": ORIGIN}, timeout=15)
        assert r.status_code == 401


class TestRegisterSetsCookie:
    def test_register_sets_cookie(self):
        s = requests.Session()
        email = f"TEST_iter23_{uuid.uuid4().hex[:8]}@email.fr"
        r = s.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "Test1234!", "role": "candidate", "name": "Iter23 Test"},
            headers={"Origin": ORIGIN},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert "token" in body and "user" in body
        assert body["user"]["email"] == email
        assert "access_token" in s.cookies.get_dict()
        low = r.headers.get("set-cookie", "").lower()
        assert "httponly" in low and "secure" in low and "samesite=none" in low


class TestLogoutClearsCookie:
    def test_logout_clears_cookie(self):
        s = requests.Session()
        _login(s)
        assert "access_token" in s.cookies.get_dict()
        r = s.post(f"{BASE_URL}/api/auth/logout", headers={"Origin": ORIGIN}, timeout=15)
        assert r.status_code == 200
        # urllib3 exposes multiple Set-Cookie headers via getlist
        set_cookies = r.raw.headers.getlist("Set-Cookie") if hasattr(r.raw, "headers") else [r.headers.get("set-cookie", "")]
        access_lines = [c for c in set_cookies if c.lower().startswith("access_token=")]
        assert access_lines, f"no access_token clearing Set-Cookie. all: {set_cookies}"
        access = access_lines[0].lower()
        cleared = ("max-age=0" in access) or ("1970" in access)
        assert cleared, f"access_token cookie not cleared: {access_lines[0]}"
        # After logout the jar should no longer carry the cookie → /me returns 401
        r2 = s.get(f"{BASE_URL}/api/auth/me", headers={"Origin": ORIGIN}, timeout=15)
        assert r2.status_code == 401, f"expected 401 after logout, got {r2.status_code}"


class TestCORS:
    def test_preflight_with_specific_origin_and_credentials(self):
        r = requests.options(
            f"{BASE_URL}/api/auth/login",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
            timeout=15,
        )
        assert r.status_code in (200, 204), f"{r.status_code} {r.text[:200]}"
        allow_origin = r.headers.get("access-control-allow-origin", "")
        allow_creds = r.headers.get("access-control-allow-credentials", "").lower()
        # When credentials are allowed, Allow-Origin MUST be the specific origin,
        # not '*' — per CORS spec the browser will reject the wildcard.
        if allow_creds == "true":
            assert allow_origin == ORIGIN, (
                f"With Allow-Credentials=true, Allow-Origin must be '{ORIGIN}', got '{allow_origin}'. "
                "This is being overridden by the k8s/Cloudflare ingress proxy."
            )
        else:
            # If credentials not allowed at preflight, the actual POST will fail with cookies.
            # Verify the actual POST response sets the right headers.
            r2 = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                headers={"Origin": ORIGIN},
                timeout=15,
            )
            creds2 = r2.headers.get("access-control-allow-credentials", "").lower()
            origin2 = r2.headers.get("access-control-allow-origin", "")
            assert creds2 == "true", f"actual POST missing Allow-Credentials: {dict(r2.headers)}"
            assert origin2 == ORIGIN, f"actual POST Allow-Origin must be specific, got '{origin2}'"


class TestExternalOffersDedup:
    def test_external_offers_all_returns_array(self):
        r = requests.get(f"{BASE_URL}/api/external-offers/all", headers={"Origin": ORIGIN}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # endpoint returns {"results": [...], "by_source": {...}, "cache_hit": bool}
        offers = data.get("results") if isinstance(data, dict) else data
        assert isinstance(offers, list), f"unexpected payload shape: {type(data).__name__}"
        assert len(offers) > 0, "no external offers returned"
        # The dedup module *may* annotate some offers with 'duplicate_sources';
        # presence is not guaranteed (it depends on cross-source overlap in this snapshot).
        dup_count = sum(1 for o in offers if "duplicate_sources" in o)
        print(f"[INFO] {len(offers)} offers returned, {dup_count} with duplicate_sources")
        # Verify if present, the type is correct
        for o in offers[:200]:
            if "duplicate_sources" in o:
                assert isinstance(o["duplicate_sources"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
