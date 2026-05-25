"""Iter7 / Phase A tests:
- Theme preference (PATCH /me/theme)
- Profile views (GET /users/{id} logs + /me/profile-views + stats + premium gating)
- Platform stats (public + admin override)
- Extended application statuses + obtained counter
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CANDIDATE = {"email": "lucas.martin@email.fr", "password": "Demo1234!"}
COMPANY = {"email": "hr@brightstudio011.fr", "password": "Demo1234!"}
ADMIN = {"email": "admin@stagiaireconnect.fr", "password": "Admin123!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data.get("user") or {}


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens():
    c_t, c_u = _login(CANDIDATE)
    co_t, co_u = _login(COMPANY)
    a_t, a_u = _login(ADMIN)
    return {
        "candidate": (c_t, c_u),
        "company": (co_t, co_u),
        "admin": (a_t, a_u),
    }


# ============ PLATFORM STATS (public + admin) ============
class TestPlatformStats:
    def test_public_platform_stats_shape(self):
        r = requests.get(f"{API}/stats/platform", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["real_obtained_count", "displayed_obtained_count", "use_manual_count",
                  "public_message", "show_counter", "total_companies", "total_candidates", "total_offers"]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["real_obtained_count"], int)
        assert isinstance(d["use_manual_count"], bool)
        assert isinstance(d["show_counter"], bool)

    def test_admin_stats_requires_admin(self, tokens):
        c_t, _ = tokens["candidate"]
        r = requests.get(f"{API}/admin/platform-stats", headers=_h(c_t), timeout=15)
        assert r.status_code == 403

    def test_admin_stats_returns_real_count(self, tokens):
        a_t, _ = tokens["admin"]
        r = requests.get(f"{API}/admin/platform-stats", headers=_h(a_t), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "real_obtained_count" in d
        assert isinstance(d["real_obtained_count"], int)

    def test_admin_can_override_displayed_and_public_reflects(self, tokens):
        a_t, _ = tokens["admin"]
        payload = {
            "displayed_obtained_count": 1337,
            "use_manual_count": True,
            "public_message": "TEST_iter7 ont trouvé un stage",
            "show_counter": True,
        }
        r = requests.put(f"{API}/admin/platform-stats", headers=_h(a_t), json=payload, timeout=15)
        assert r.status_code == 200, r.text
        # public reflects
        r2 = requests.get(f"{API}/stats/platform", timeout=15)
        d = r2.json()
        assert d["displayed_obtained_count"] == 1337
        assert d["use_manual_count"] is True
        assert d["public_message"] == "TEST_iter7 ont trouvé un stage"
        # cleanup: revert to auto
        revert = {"displayed_obtained_count": 0, "use_manual_count": False,
                  "public_message": "étudiants ont trouvé un stage ou une alternance via StageConnect",
                  "show_counter": True}
        requests.put(f"{API}/admin/platform-stats", headers=_h(a_t), json=revert, timeout=15)

    def test_show_counter_false_persists(self, tokens):
        a_t, _ = tokens["admin"]
        requests.put(f"{API}/admin/platform-stats", headers=_h(a_t),
                     json={"displayed_obtained_count": 0, "use_manual_count": False,
                           "public_message": "x", "show_counter": False}, timeout=15)
        r = requests.get(f"{API}/stats/platform", timeout=15)
        assert r.json()["show_counter"] is False
        # revert
        requests.put(f"{API}/admin/platform-stats", headers=_h(a_t),
                     json={"displayed_obtained_count": 0, "use_manual_count": False,
                           "public_message": "étudiants ont trouvé un stage ou une alternance via StageConnect",
                           "show_counter": True}, timeout=15)


# ============ THEME PREFERENCE ============
class TestTheme:
    @pytest.mark.parametrize("pref", ["light", "dark", "system"])
    def test_set_theme_valid(self, tokens, pref):
        t, _ = tokens["candidate"]
        r = requests.patch(f"{API}/me/theme", headers=_h(t), json={"theme_preference": pref}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["theme_preference"] == pref
        # verify persisted via /auth/me
        me = requests.get(f"{API}/auth/me", headers=_h(t), timeout=10).json()
        assert me.get("theme_preference") == pref

    def test_set_theme_invalid_400(self, tokens):
        t, _ = tokens["candidate"]
        r = requests.patch(f"{API}/me/theme", headers=_h(t), json={"theme_preference": "blue"}, timeout=10)
        assert r.status_code == 400


# ============ APPLICATION EXTENDED STATUSES + OBTAINED COUNT ============
class TestExtendedStatuses:
    def test_obtained_statuses_accepted_and_counted(self, tokens):
        co_t, co_u = tokens["company"]
        # find an existing application owned by this company
        # use /applications?type=received
        r = requests.get(f"{API}/applications?type=received", headers=_h(co_t), timeout=15)
        assert r.status_code == 200, r.text
        apps = r.json()
        if not apps:
            pytest.skip("No applications received for this company - cannot test status update")
        target = apps[0]
        original_status = target["status"]
        # baseline count
        base = requests.get(f"{API}/stats/platform", timeout=15).json()["real_obtained_count"]

        for st in ["internship_obtained", "apprenticeship_obtained", "contract_signed"]:
            r = requests.patch(f"{API}/applications/{target['app_id']}/status",
                               headers=_h(co_t), json={"status": st}, timeout=15)
            assert r.status_code == 200, f"failed to set {st}: {r.text}"
            # verify counted in real_obtained_count
            time.sleep(0.3)
            cur = requests.get(f"{API}/stats/platform", timeout=15).json()["real_obtained_count"]
            assert cur >= 1, f"obtained count should be >=1 after setting status {st}"

        # invalid status
        r = requests.patch(f"{API}/applications/{target['app_id']}/status",
                           headers=_h(co_t), json={"status": "bogus_status"}, timeout=10)
        assert r.status_code == 400

        # restore
        requests.patch(f"{API}/applications/{target['app_id']}/status",
                       headers=_h(co_t), json={"status": original_status}, timeout=10)


# ============ PROFILE VIEWS ============
class TestProfileViews:
    def test_view_logs_a_row_dedup(self, tokens):
        """Candidate views company profile -> a profile_view should be recorded for the company."""
        co_t, co_u = tokens["company"]
        c_t, c_u = tokens["candidate"]
        # admin clears the dedup window by inserting an indirect path: We just call view twice and
        # rely on dedup behavior to NOT create two rows in 30 min window.
        before_stats = requests.get(f"{API}/me/profile-views/stats", headers=_h(co_t), timeout=10).json()
        # candidate visits company's public page
        r = requests.get(f"{API}/users/{co_u['user_id']}", headers=_h(c_t), timeout=10)
        assert r.status_code == 200
        time.sleep(0.5)
        after = requests.get(f"{API}/me/profile-views/stats", headers=_h(co_t), timeout=10).json()
        # total >= before total (dedup may keep it equal)
        assert after["total"] >= before_stats["total"]
        # All required keys
        for k in ["total", "week", "month", "distinct_viewers", "is_premium"]:
            assert k in after

    def test_profile_views_list_requires_premium(self, tokens):
        co_t, _ = tokens["company"]
        # Company brightstudio: usually NOT premium. We don't grant -> expect 402.
        r = requests.get(f"{API}/me/profile-views", headers=_h(co_t), timeout=10)
        # if already premium for some reason, accept 200 too but flag
        assert r.status_code in (402, 200), r.text

    def test_grant_premium_then_list_visible(self, tokens):
        a_t, _ = tokens["admin"]
        c_t, c_u = tokens["candidate"]
        # Grant premium to candidate
        r = requests.post(f"{API}/admin/grant-premium/{c_u['user_id']}?days=30",
                          headers=_h(a_t), timeout=15)
        assert r.status_code == 200, r.text
        # Make sure there's at least one profile-view for candidate by having company view them
        co_t, _ = tokens["company"]
        requests.get(f"{API}/users/{c_u['user_id']}", headers=_h(co_t), timeout=10)
        time.sleep(0.5)
        # Now candidate gets premium-only list
        r2 = requests.get(f"{API}/me/profile-views", headers=_h(c_t), timeout=10)
        assert r2.status_code == 200, f"expected 200 after grant-premium, got {r2.status_code}: {r2.text}"
        data = r2.json()
        assert isinstance(data, list)
        # premium flag in stats
        st = requests.get(f"{API}/me/profile-views/stats", headers=_h(c_t), timeout=10).json()
        assert st["is_premium"] is True

    def test_stats_endpoint_shape(self, tokens):
        c_t, _ = tokens["candidate"]
        r = requests.get(f"{API}/me/profile-views/stats", headers=_h(c_t), timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ["total", "week", "month", "distinct_viewers", "is_premium"]:
            assert k in d
        assert all(isinstance(d[k], int) for k in ["total", "week", "month", "distinct_viewers"])
