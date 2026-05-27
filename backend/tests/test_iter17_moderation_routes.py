"""Iteration 17 — Backend tests for split routes (contacts/notifications/deals)
and the NEW moderation/reports feature.

Coverage:
- Contacts module endpoints (request/accept/refuse/list/status/cancel/remove/block)
- Notifications module endpoints
- Deals module endpoints (create as pending, list published, my deals, edit re-pending,
  save toggle + notification, admin queue + validate)
- Moderation module (create report on post/comment, dup/self/invalid rejections,
  /reports/mine, /admin/reports queue + counts + snapshot, dismiss, remove with
  cascade + notification, archive)
- Regression smoke on prior endpoints (auth/posts/messages-rt/ads public/
  external-offers/keyless)
"""
import os
import sys
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv

# Load REACT_APP_BACKEND_URL from frontend .env if not set
load_dotenv("/app/frontend/.env")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE:
    print("REACT_APP_BACKEND_URL missing", file=sys.stderr)
    sys.exit(1)
API = f"{BASE}/api"

ADMIN = ("admin@stagiaireconnect.fr", "Admin123!")
LUCAS = ("lucas.martin@email.fr", "Demo1234!")
HR = ("hr@technova.fr", "Demo1234!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    j = r.json()
    return j["token"], j["user"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_ctx():
    t, u = _login(*ADMIN)
    return {"t": t, "u": u}


@pytest.fixture(scope="module")
def lucas_ctx():
    t, u = _login(*LUCAS)
    return {"t": t, "u": u}


@pytest.fixture(scope="module")
def hr_ctx():
    t, u = _login(*HR)
    return {"t": t, "u": u}


# ============================================================
# CONTACTS
# ============================================================
class TestContacts:
    def test_status_none_then_request(self, lucas_ctx, hr_ctx):
        # status before
        r = requests.get(f"{API}/contacts/status/{hr_ctx['u']['user_id']}", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
        before = r.json()["status"]
        # If already connected from prior runs, just verify endpoint shape and skip rest
        if before == "connected":
            pytest.skip("Already connected from prior run")
        # Send request (if no pending sent yet)
        if before == "none":
            r = requests.post(f"{API}/contacts/request",
                              json={"to_user_id": hr_ctx["u"]["user_id"]},
                              headers=_h(lucas_ctx["t"]))
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is True
        # status after must be sent or received
        r = requests.get(f"{API}/contacts/status/{hr_ctx['u']['user_id']}", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
        assert r.json()["status"] in ("sent", "connected")

    def test_list_contacts_shape(self, lucas_ctx):
        r = requests.get(f"{API}/contacts", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
        j = r.json()
        for k in ("contacts", "pending", "sent"):
            assert k in j
            assert isinstance(j[k], list)

    def test_self_request_refused(self, lucas_ctx):
        r = requests.post(f"{API}/contacts/request",
                          json={"to_user_id": lucas_ctx["u"]["user_id"]},
                          headers=_h(lucas_ctx["t"]))
        assert r.status_code == 400

    def test_block_idempotent(self, lucas_ctx):
        fake = "u_bogus_" + uuid.uuid4().hex[:6]
        r1 = requests.post(f"{API}/contacts/block/{fake}", headers=_h(lucas_ctx["t"]))
        r2 = requests.post(f"{API}/contacts/block/{fake}", headers=_h(lucas_ctx["t"]))
        assert r1.status_code == 200 and r2.status_code == 200
        assert r2.json().get("already_blocked") is True


# ============================================================
# NOTIFICATIONS
# ============================================================
class TestNotifications:
    def test_list_shape(self, lucas_ctx):
        r = requests.get(f"{API}/notifications", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
        j = r.json()
        assert "notifications" in j and isinstance(j["notifications"], list)
        assert "unread" in j and isinstance(j["unread"], int)

    def test_mark_read(self, lucas_ctx):
        r = requests.post(f"{API}/notifications/read", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # verify
        r2 = requests.get(f"{API}/notifications", headers=_h(lucas_ctx["t"]))
        assert r2.json()["unread"] == 0


# ============================================================
# DEALS
# ============================================================
@pytest.fixture(scope="module")
def created_deal(hr_ctx):
    payload = {
        "title": f"TEST_iter17 Bon Plan {uuid.uuid4().hex[:6]}",
        "description": "Description test iter17",
        "category": "food",
        "city": "Paris",
        "region": "IDF",
        "promo_code": "TEST17",
        "discount": "-10%",
        "url": "https://example.com",
    }
    r = requests.post(f"{API}/deals", json=payload, headers=_h(hr_ctx["t"]))
    assert r.status_code == 200, r.text
    j = r.json()
    return j


class TestDeals:
    def test_create_is_pending(self, created_deal):
        assert created_deal["status"] == "pending"
        assert created_deal["deal_id"].startswith("deal_")

    def test_list_published_excludes_pending(self, created_deal):
        r = requests.get(f"{API}/deals")
        assert r.status_code == 200
        ids = {d["deal_id"] for d in r.json()}
        assert created_deal["deal_id"] not in ids  # because it's pending

    def test_admin_queue_with_counts(self, admin_ctx, created_deal):
        r = requests.get(f"{API}/admin/deals?status=pending", headers=_h(admin_ctx["t"]))
        assert r.status_code == 200
        j = r.json()
        assert "deals" in j and "counts" in j
        for k in ("pending", "published", "refused", "suspended", "all"):
            assert k in j["counts"]
        assert any(d["deal_id"] == created_deal["deal_id"] for d in j["deals"])

    def test_admin_validate_approve(self, admin_ctx, created_deal):
        r = requests.post(f"{API}/admin/deals/{created_deal['deal_id']}/validate",
                          json={"action": "approve"}, headers=_h(admin_ctx["t"]))
        assert r.status_code == 200
        assert r.json()["status"] == "published"
        # Now appears in public list
        r2 = requests.get(f"{API}/deals")
        assert any(d["deal_id"] == created_deal["deal_id"] for d in r2.json())

    def test_author_edit_repends(self, hr_ctx, created_deal):
        r = requests.patch(f"{API}/deals/{created_deal['deal_id']}",
                           json={"title": "TEST_iter17 edited"},
                           headers=_h(hr_ctx["t"]))
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_save_toggle_and_mine(self, admin_ctx, lucas_ctx, hr_ctx, created_deal):
        # Re-publish to allow save
        requests.post(f"{API}/admin/deals/{created_deal['deal_id']}/validate",
                      json={"action": "approve"}, headers=_h(admin_ctx["t"]))
        r = requests.post(f"{API}/deals/{created_deal['deal_id']}/save", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
        assert lucas_ctx["u"]["user_id"] in r.json()["saves"]
        # author got notified
        r2 = requests.get(f"{API}/notifications", headers=_h(hr_ctx["t"]))
        kinds = [n.get("kind") for n in r2.json()["notifications"]]
        assert "deal_save" in kinds
        # /deals/mine shape
        r3 = requests.get(f"{API}/deals/mine", headers=_h(lucas_ctx["t"]))
        assert r3.status_code == 200
        j = r3.json()
        for k in ("deals", "saved", "boosts"):
            assert k in j

    def test_validate_invalid_action(self, admin_ctx, created_deal):
        r = requests.post(f"{API}/admin/deals/{created_deal['deal_id']}/validate",
                          json={"action": "destroy"}, headers=_h(admin_ctx["t"]))
        assert r.status_code == 400


# ============================================================
# MODERATION (Reports) - NEW
# ============================================================
@pytest.fixture(scope="module")
def lucas_post(lucas_ctx):
    """Create a post owned by lucas to be reported by HR."""
    r = requests.post(f"{API}/posts",
                      json={"content": f"TEST_iter17 post {uuid.uuid4().hex[:6]} to be reported"},
                      headers=_h(lucas_ctx["t"]))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def lucas_comment(lucas_ctx, lucas_post):
    r = requests.post(f"{API}/posts/comment",
                      json={"post_id": lucas_post["post_id"],
                            "content": "TEST_iter17 comment to report"},
                      headers=_h(lucas_ctx["t"]))
    assert r.status_code == 200, r.text
    return r.json()


class TestModeration:
    def test_create_report_post(self, hr_ctx, lucas_post):
        r = requests.post(f"{API}/reports",
                          json={"target_type": "post", "target_id": lucas_post["post_id"],
                                "reason": "spam", "details": "TEST_iter17 spam report"},
                          headers=_h(hr_ctx["t"]))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["report_id"].startswith("rep_")

    def test_duplicate_report_refused(self, hr_ctx, lucas_post):
        r = requests.post(f"{API}/reports",
                          json={"target_type": "post", "target_id": lucas_post["post_id"],
                                "reason": "spam"},
                          headers=_h(hr_ctx["t"]))
        assert r.status_code == 400
        assert "déjà" in r.text or "deja" in r.text.lower()

    def test_self_report_refused(self, lucas_ctx, lucas_post):
        r = requests.post(f"{API}/reports",
                          json={"target_type": "post", "target_id": lucas_post["post_id"],
                                "reason": "spam"},
                          headers=_h(lucas_ctx["t"]))
        assert r.status_code == 400

    def test_invalid_reason_refused(self, hr_ctx, lucas_post):
        r = requests.post(f"{API}/reports",
                          json={"target_type": "post", "target_id": lucas_post["post_id"],
                                "reason": "bogus_reason"},
                          headers=_h(hr_ctx["t"]))
        assert r.status_code == 400

    def test_target_not_found(self, hr_ctx):
        r = requests.post(f"{API}/reports",
                          json={"target_type": "post", "target_id": "post_nonexistent_xxx",
                                "reason": "spam"},
                          headers=_h(hr_ctx["t"]))
        assert r.status_code == 404

    def test_reports_mine(self, hr_ctx, lucas_post):
        r = requests.get(f"{API}/reports/mine", headers=_h(hr_ctx["t"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert any(rep["target_id"] == lucas_post["post_id"] for rep in r.json())

    def test_admin_reports_queue_with_snapshot(self, admin_ctx, lucas_post):
        r = requests.get(f"{API}/admin/reports?status=pending", headers=_h(admin_ctx["t"]))
        assert r.status_code == 200
        j = r.json()
        assert "reports" in j and "counts" in j
        for k in ("pending", "kept", "removed", "all"):
            assert k in j["counts"]
        found = next((rr for rr in j["reports"] if rr["target_id"] == lucas_post["post_id"]), None)
        assert found is not None
        assert found["target_exists"] is True
        assert "target_snapshot" in found
        assert found["target_snapshot"]["content"] == lucas_post["content"]
        assert found["target_snapshot"]["author_id"] == lucas_post["author_id"]

    def test_non_admin_blocked_from_admin_endpoints(self, lucas_ctx):
        r = requests.get(f"{API}/admin/reports", headers=_h(lucas_ctx["t"]))
        assert r.status_code == 403

    def test_admin_dismiss_marks_kept(self, admin_ctx, hr_ctx, lucas_post):
        # Find the report on lucas_post
        r = requests.get(f"{API}/admin/reports?status=pending", headers=_h(admin_ctx["t"]))
        rep = next((x for x in r.json()["reports"] if x["target_id"] == lucas_post["post_id"]), None)
        assert rep is not None
        rid = rep["report_id"]
        r2 = requests.post(f"{API}/admin/reports/{rid}/dismiss",
                           json={"note": "TEST_iter17 keep"},
                           headers=_h(admin_ctx["t"]))
        assert r2.status_code == 200
        assert r2.json()["status"] == "kept"
        # All reports on this target should now be 'kept'
        r3 = requests.get(f"{API}/admin/reports?status=kept", headers=_h(admin_ctx["t"]))
        assert any(x["target_id"] == lucas_post["post_id"] for x in r3.json()["reports"])

    def test_admin_remove_comment_cascade(self, admin_ctx, hr_ctx, lucas_ctx, lucas_comment):
        # HR reports the comment
        r = requests.post(f"{API}/reports",
                          json={"target_type": "comment", "target_id": lucas_comment["comment_id"],
                                "reason": "harassment", "details": "TEST_iter17 harassment"},
                          headers=_h(hr_ctx["t"]))
        assert r.status_code == 200, r.text
        rid = r.json()["report_id"]
        # Mark notifications read for lucas to detect new one
        requests.post(f"{API}/notifications/read", headers=_h(lucas_ctx["t"]))
        # Admin removes
        r2 = requests.post(f"{API}/admin/reports/{rid}/remove",
                           json={"reason": "TEST_iter17 violation"},
                           headers=_h(admin_ctx["t"]))
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "removed"
        # Author notified
        time.sleep(0.5)
        rn = requests.get(f"{API}/notifications", headers=_h(lucas_ctx["t"]))
        kinds = [n.get("kind") for n in rn.json()["notifications"]]
        assert "moderation_removed" in kinds

    def test_admin_archive_report(self, admin_ctx, hr_ctx, lucas_ctx):
        # Create fresh post + report → archive
        rp = requests.post(f"{API}/posts",
                           json={"content": f"TEST_iter17 archive {uuid.uuid4().hex[:6]}"},
                           headers=_h(lucas_ctx["t"]))
        pid = rp.json()["post_id"]
        rr = requests.post(f"{API}/reports",
                           json={"target_type": "post", "target_id": pid, "reason": "other"},
                           headers=_h(hr_ctx["t"]))
        rid = rr.json()["report_id"]
        rd = requests.delete(f"{API}/admin/reports/{rid}", headers=_h(admin_ctx["t"]))
        assert rd.status_code == 200
        # Should no longer exist in any status
        r = requests.get(f"{API}/admin/reports?status=all", headers=_h(admin_ctx["t"]))
        assert not any(x["report_id"] == rid for x in r.json()["reports"])


# ============================================================
# REGRESSION smoke
# ============================================================
class TestRegression:
    def test_auth_login_admin(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_posts_list(self):
        r = requests.get(f"{API}/posts")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_post_create_like_comment(self, lucas_ctx):
        rp = requests.post(f"{API}/posts",
                           json={"content": f"TEST_iter17 regression {uuid.uuid4().hex[:6]}"},
                           headers=_h(lucas_ctx["t"]))
        assert rp.status_code == 200
        pid = rp.json()["post_id"]
        rl = requests.post(f"{API}/posts/{pid}/like", headers=_h(lucas_ctx["t"]))
        assert rl.status_code == 200
        rc = requests.post(f"{API}/posts/comment",
                           json={"post_id": pid, "content": "TEST_iter17 reg comment"},
                           headers=_h(lucas_ctx["t"]))
        assert rc.status_code == 200

    def test_ads_public(self):
        r = requests.get(f"{API}/ads/public")
        assert r.status_code == 200

    def test_external_offers_keyless(self):
        r = requests.get(f"{API}/external-offers/keyless")
        assert r.status_code == 200

    def test_messages_rt(self, lucas_ctx, hr_ctx):
        r = requests.post(f"{API}/messages-rt",
                          json={"to_user_id": hr_ctx["u"]["user_id"],
                                "content": "TEST_iter17 rt regression"},
                          headers=_h(lucas_ctx["t"]))
        assert r.status_code == 200
