"""Iteration 24 — Password reset + email verification flows.

Covers: /api/auth/forgot-password, /api/auth/reset-password,
/api/auth/send-verification, /api/auth/verify-email, /api/admin/auth-tokens/recent.
"""
import os
import secrets
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "bernardolivieri1326@gmail.com"
ADMIN_PASSWORD = "OwnerAdmin2026!"
CANDIDATE_EMAIL = "lucas.martin@email.fr"
CANDIDATE_PASSWORD = "Demo1234!"


# ---------- shared fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    token = r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def candidate_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": CANDIDATE_EMAIL, "password": CANDIDATE_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    token = r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _recent_tokens(admin_session):
    r = admin_session.get(f"{API}/admin/auth-tokens/recent", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- forgot-password ----------
class TestForgotPassword:
    def test_known_email_returns_ok_and_creates_token(self, admin_session):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": CANDIDATE_EMAIL}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert "message" in body
        time.sleep(0.5)
        recent = _recent_tokens(admin_session)
        emails = [t["email"] for t in recent["password_reset"]]
        assert CANDIDATE_EMAIL in emails, f"reset token not persisted, got: {emails}"
        match = [t for t in recent["password_reset"] if t["email"] == CANDIDATE_EMAIL][0]
        assert isinstance(match["token"], str) and len(match["token"]) > 20
        assert match["used"] is False
        assert match["expires_at"]  # expiry set

    def test_unknown_email_returns_ok_no_token_created(self, admin_session):
        before = _recent_tokens(admin_session)
        before_count = len(before["password_reset"])
        unknown = f"test_unknown_{secrets.token_hex(4)}@example.com"
        r = requests.post(f"{API}/auth/forgot-password", json={"email": unknown}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        time.sleep(0.3)
        after = _recent_tokens(admin_session)
        emails_after = [t["email"] for t in after["password_reset"]]
        assert unknown not in emails_after
        # admin endpoint never reveals enumeration: also no new entry total
        assert len(after["password_reset"]) <= before_count + 0  # allow same; never grows for unknown


# ---------- reset-password ----------
class TestResetPassword:
    @pytest.fixture(scope="class")
    def fresh_reset_token(self, admin_session):
        # Generate a fresh reset token for a disposable user
        email = f"test_reset_{secrets.token_hex(4)}@example.com"
        password = "InitialPass1!"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "password": password, "role": "candidate", "name": "Reset Test"
        }, timeout=20)
        assert r.status_code == 200, r.text
        # Request reset
        r2 = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=15)
        assert r2.status_code == 200
        time.sleep(0.5)
        recent = _recent_tokens(admin_session)
        match = next((t for t in recent["password_reset"] if t["email"] == email), None)
        assert match, "fresh reset token not found"
        return {"email": email, "token": match["token"]}

    def test_invalid_token_returns_400(self):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": "totally-invalid-token-xyz", "password": "NewPass1234!"},
                          timeout=15)
        assert r.status_code == 400
        assert "invalide" in (r.json().get("detail", "").lower())

    def test_short_password_returns_400(self, fresh_reset_token):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": fresh_reset_token["token"], "password": "short"},
                          timeout=15)
        assert r.status_code == 400

    def test_reset_success_then_login_with_new_password(self, fresh_reset_token):
        new_password = "BrandNewPass99!"
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": fresh_reset_token["token"], "password": new_password},
                          timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # Login with NEW password
        login = requests.post(f"{API}/auth/login",
                              json={"email": fresh_reset_token["email"], "password": new_password},
                              timeout=20)
        assert login.status_code == 200, login.text
        assert "token" in login.json()

    def test_replay_same_token_returns_400(self, fresh_reset_token):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": fresh_reset_token["token"], "password": "AnotherPass2026!"},
                          timeout=15)
        assert r.status_code == 400
        assert "déjà" in r.json().get("detail", "").lower() or "utilis" in r.json().get("detail", "").lower()


# ---------- send-verification + verify-email ----------
class TestEmailVerification:
    @pytest.fixture(scope="class")
    def verif_token(self, admin_session):
        # Use admin session to trigger send-verification
        # Need a fresh user that hasn't verified yet to test the flip
        email = f"test_verify_{secrets.token_hex(4)}@example.com"
        password = "VerifyTest1!"
        reg = requests.post(f"{API}/auth/register", json={
            "email": email, "password": password, "role": "candidate", "name": "Verify Test"
        }, timeout=20)
        assert reg.status_code == 200, reg.text
        user_token = reg.json().get("token")
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {user_token}"})
        r = s.post(f"{API}/auth/send-verification", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("delivery", {}).get("provider") == "console"
        assert body.get("delivery", {}).get("ok") is True
        time.sleep(0.5)
        recent = _recent_tokens(admin_session)
        match = next((t for t in recent["email_verification"] if t["email"] == email), None)
        assert match, "verification token not found"
        return {"email": email, "token": match["token"], "user_session": s}

    def test_send_verification_returns_console_delivery(self, verif_token):
        # Already exercised by fixture; assert structure here
        assert verif_token["token"]

    def test_verify_invalid_token_returns_400(self):
        r = requests.get(f"{API}/auth/verify-email", params={"token": "nope-not-a-real-token"}, timeout=15)
        assert r.status_code == 400

    def test_verify_valid_token_flips_email_verified(self, verif_token):
        r = requests.get(f"{API}/auth/verify-email", params={"token": verif_token["token"]}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # Confirm via /auth/me that email_verified=true now
        me = verif_token["user_session"].get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200
        assert me.json().get("email_verified") is True

    def test_replay_verify_token_returns_400(self, verif_token):
        r = requests.get(f"{API}/auth/verify-email", params={"token": verif_token["token"]}, timeout=15)
        assert r.status_code == 400


# ---------- admin debug endpoint guard ----------
class TestAdminAuthTokensRBAC:
    def test_candidate_forbidden(self, candidate_session):
        r = candidate_session.get(f"{API}/admin/auth-tokens/recent", timeout=15)
        assert r.status_code == 403

    def test_admin_allowed_returns_lists(self, admin_session):
        r = admin_session.get(f"{API}/admin/auth-tokens/recent", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "password_reset" in body
        assert "email_verification" in body
        assert "provider" in body
        assert body["provider"]["provider"] == "console"
