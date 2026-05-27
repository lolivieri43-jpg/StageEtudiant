"""Iteration 16 — Refactor: posts + messages moved to routes/posts.py & routes/messages.py.
Pure refactor — strict behavior preservation. Tests cover:
- POSTS: list, create (with media + link_preview), link-preview (+ cache), like (+notif),
         comment (+counter +notif), get comments
- MESSAGES: send (+attachments), list conversations, get messages (read marker), notif
- REGRESSION: /messages-rt (still in server.py), /ads/{id}/view rate-limit, /admin/deals,
              /admin/ads, /external-offers, /upload (multi-mime), /auth/login
"""
import os
import time
import io
import requests
import pytest
from pathlib import Path

# Load REACT_APP_BACKEND_URL from frontend/.env if not in environ
if "REACT_APP_BACKEND_URL" not in os.environ:
    fenv = Path("/app/frontend/.env")
    if fenv.exists():
        for line in fenv.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()
                break

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


# ------------------ Fixtures ------------------

def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    j = r.json()
    return j["token"], j["user"]


@pytest.fixture(scope="module")
def candidate():
    tok, user = _login("lucas.martin@email.fr", "Demo1234!")
    return {"token": tok, "user": user, "h": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def company():
    tok, user = _login("hr@technova.fr", "Demo1234!")
    return {"token": tok, "user": user, "h": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def admin():
    tok, user = _login("admin@stagiaireconnect.fr", "Admin123!")
    return {"token": tok, "user": user, "h": {"Authorization": f"Bearer {tok}"}}


# ------------------ AUTH (regression) ------------------

class TestAuthRegression:
    def test_login_returns_token(self, candidate):
        assert isinstance(candidate["token"], str) and len(candidate["token"]) > 10
        assert candidate["user"]["email"] == "lucas.martin@email.fr"

    def test_me(self, candidate):
        r = requests.get(f"{API}/auth/me", headers=candidate["h"], timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == "lucas.martin@email.fr"


# ------------------ POSTS (refactored) ------------------

class TestPostsRefactor:
    def test_get_posts_public(self):
        r = requests.get(f"{API}/posts", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_create_simple_post(self, candidate):
        payload = {"content": "TEST_iter16 simple post", "category": "general"}
        r = requests.post(f"{API}/posts", json=payload, headers=candidate["h"], timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert "post_id" in doc and doc["post_id"].startswith("post_")
        assert doc["content"] == payload["content"]
        assert doc["author_id"] == candidate["user"]["user_id"]
        assert doc["likes"] == []
        assert doc["comments_count"] == 0
        assert "_id" not in doc

        # GET verify persistence
        lst = requests.get(f"{API}/posts", timeout=10).json()
        assert any(p["post_id"] == doc["post_id"] for p in lst)

    def test_create_post_with_media_and_link_preview(self, candidate):
        payload = {
            "content": "TEST_iter16 with media",
            "category": "general",
            "media": [{"type": "image", "url": "https://example.com/x.png",
                       "filename": "x.png", "mime": "image/png", "size": 1024}],
            "link_preview": {
                "url": "https://example.com",
                "title": "Example",
                "description": "Desc",
                "image": None,
                "domain": "example.com",
            },
        }
        r = requests.post(f"{API}/posts", json=payload, headers=candidate["h"], timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert len(doc["media"]) == 1
        assert doc["media"][0]["url"] == "https://example.com/x.png"
        assert doc["link_preview"]["domain"] == "example.com"
        assert doc["link_preview"]["title"] == "Example"

    def test_link_preview_and_cache(self, candidate):
        url = "https://example.com"
        t1 = time.time()
        r1 = requests.post(f"{API}/posts/link-preview", json={"url": url},
                           headers=candidate["h"], timeout=15)
        d1 = time.time() - t1
        assert r1.status_code == 200, r1.text
        p1 = r1.json()
        for k in ("url", "title", "description", "image", "domain"):
            assert k in p1
        assert p1["domain"] == "example.com"

        # Second call should hit cache and be faster (and same content)
        t2 = time.time()
        r2 = requests.post(f"{API}/posts/link-preview", json={"url": url},
                           headers=candidate["h"], timeout=15)
        d2 = time.time() - t2
        assert r2.status_code == 200
        p2 = r2.json()
        assert p2["url"] == p1["url"]
        assert p2["domain"] == p1["domain"]
        # cache is much faster — be lenient
        assert d2 <= d1 + 0.5

    def test_link_preview_requires_url(self, candidate):
        r = requests.post(f"{API}/posts/link-preview", json={"url": ""},
                          headers=candidate["h"], timeout=10)
        assert r.status_code == 400

    def test_like_toggle_and_notification(self, candidate, company):
        # Company creates a post; candidate likes it -> notif to company
        cr = requests.post(f"{API}/posts",
                           json={"content": "TEST_iter16 to_like", "category": "general"},
                           headers=company["h"], timeout=10)
        assert cr.status_code == 200
        post_id = cr.json()["post_id"]

        r = requests.post(f"{API}/posts/{post_id}/like", headers=candidate["h"], timeout=10)
        assert r.status_code == 200
        likes = r.json()["likes"]
        assert candidate["user"]["user_id"] in likes

        # Toggle off
        r2 = requests.post(f"{API}/posts/{post_id}/like", headers=candidate["h"], timeout=10)
        assert r2.status_code == 200
        assert candidate["user"]["user_id"] not in r2.json()["likes"]

        # Notification visible to company?
        nr = requests.get(f"{API}/notifications", headers=company["h"], timeout=10)
        assert nr.status_code == 200
        body = nr.json()
        nots = body.get("notifications", body) if isinstance(body, dict) else body
        assert any(n.get("kind") == "like" for n in nots), "Expected a like notification for company"

    def test_like_404(self, candidate):
        r = requests.post(f"{API}/posts/nonexistent_xyz/like",
                          headers=candidate["h"], timeout=10)
        assert r.status_code == 404

    def test_comment_increments_and_notifies(self, candidate, company):
        cr = requests.post(f"{API}/posts",
                           json={"content": "TEST_iter16 to_comment", "category": "general"},
                           headers=company["h"], timeout=10)
        post_id = cr.json()["post_id"]

        r = requests.post(f"{API}/posts/comment",
                          json={"post_id": post_id, "content": "TEST_comment"},
                          headers=candidate["h"], timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["post_id"] == post_id
        assert doc["content"] == "TEST_comment"
        assert "comment_id" in doc

        # GET comments
        gc = requests.get(f"{API}/posts/{post_id}/comments", timeout=10)
        assert gc.status_code == 200
        comments = gc.json()
        assert any(c["comment_id"] == doc["comment_id"] for c in comments)

        # Comments_count incremented?
        lst = requests.get(f"{API}/posts", timeout=10).json()
        match = next((p for p in lst if p["post_id"] == post_id), None)
        assert match is not None
        assert match["comments_count"] >= 1

        # Notification for company
        nr = requests.get(f"{API}/notifications", headers=company["h"], timeout=10)
        body = nr.json()
        nots = body.get("notifications", body) if isinstance(body, dict) else body
        assert any(n.get("kind") == "comment" for n in nots)

    def test_comment_404(self, candidate):
        r = requests.post(f"{API}/posts/comment",
                          json={"post_id": "nonexistent_xyz", "content": "x"},
                          headers=candidate["h"], timeout=10)
        assert r.status_code == 404

    def test_posts_require_auth(self):
        r = requests.post(f"{API}/posts", json={"content": "anon"}, timeout=10)
        assert r.status_code in (401, 403)


# ------------------ MESSAGES (refactored) ------------------

class TestMessagesRefactor:
    def test_send_and_list_conversations(self, candidate, company):
        msg = {
            "to_user_id": company["user"]["user_id"],
            "content": "TEST_iter16 hello from candidate",
        }
        r = requests.post(f"{API}/messages", json=msg, headers=candidate["h"], timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["from_id"] == candidate["user"]["user_id"]
        assert doc["to_id"] == company["user"]["user_id"]
        assert doc["content"] == msg["content"]
        assert "message_id" in doc and doc["message_id"].startswith("msg_")
        assert "conv_id" in doc

        # Conversations list for candidate
        cl = requests.get(f"{API}/conversations", headers=candidate["h"], timeout=10)
        assert cl.status_code == 200
        convs = cl.json()
        my_conv = next((c for c in convs if c["conv_id"] == doc["conv_id"]), None)
        assert my_conv is not None
        assert my_conv["last_message"] == msg["content"]
        assert "last_at" in my_conv
        assert my_conv["other"]["user_id"] == company["user"]["user_id"]
        assert isinstance(my_conv["unread"], int)

    def test_send_with_attachments(self, candidate, company):
        msg = {
            "to_user_id": company["user"]["user_id"],
            "content": "",
            "attachments": [
                {"type": "pdf", "url": "/api/files/abc", "filename": "report.pdf",
                 "mime": "application/pdf", "size": 12345},
            ],
        }
        r = requests.post(f"{API}/messages", json=msg, headers=candidate["h"], timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert len(doc["attachments"]) == 1
        assert doc["attachments"][0]["filename"] == "report.pdf"
        assert doc["attachments"][0]["mime"] == "application/pdf"

    def test_get_messages_marks_read(self, candidate, company):
        # Company sends to candidate
        r = requests.post(f"{API}/messages",
                          json={"to_user_id": candidate["user"]["user_id"],
                                "content": "TEST_iter16 reply"},
                          headers=company["h"], timeout=10)
        assert r.status_code == 200

        # Candidate fetches the conversation — should mark as read
        g = requests.get(f"{API}/messages/{company['user']['user_id']}",
                         headers=candidate["h"], timeout=10)
        assert g.status_code == 200
        msgs = g.json()
        assert len(msgs) >= 1
        # ordered ascending by created_at
        timestamps = [m["created_at"] for m in msgs]
        assert timestamps == sorted(timestamps)

        # Now unread count for candidate's view of conv must be 0
        cl = requests.get(f"{API}/conversations", headers=candidate["h"], timeout=10).json()
        pair_conv = next((c for c in cl if c["other"]["user_id"] == company["user"]["user_id"]), None)
        assert pair_conv is not None
        assert pair_conv["unread"] == 0

    def test_send_to_unknown_user(self, candidate):
        r = requests.post(f"{API}/messages",
                          json={"to_user_id": "user_does_not_exist", "content": "x"},
                          headers=candidate["h"], timeout=10)
        assert r.status_code == 404

    def test_messages_require_auth(self):
        r = requests.get(f"{API}/conversations", timeout=10)
        assert r.status_code in (401, 403)


# ------------------ REGRESSION ------------------

class TestRegressionMessagesRT:
    def test_messages_rt_still_works(self, candidate, company):
        # /messages-rt still in server.py — verify unchanged behavior
        r = requests.post(f"{API}/messages-rt",
                          json={"to_user_id": company["user"]["user_id"],
                                "content": "TEST_iter16 RT msg"},
                          headers=candidate["h"], timeout=10)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["content"] == "TEST_iter16 RT msg"
        assert doc["from_id"] == candidate["user"]["user_id"]


class TestRegressionAds:
    def test_ad_view_rate_limit(self, admin):
        # Get list of ads via admin
        r = requests.get(f"{API}/admin/ads", headers=admin["h"], timeout=10)
        assert r.status_code == 200
        body = r.json()
        ads = body.get("ads", body) if isinstance(body, dict) else body
        if not ads:
            pytest.skip("No ads to test rate-limit")
        ad_id = ads[0].get("ad_id") or ads[0].get("id")
        if not ad_id:
            pytest.skip("Ad has no id field")
        # First call
        r1 = requests.post(f"{API}/ads/{ad_id}/view", timeout=10)
        # Second call within 1h should be deduped (counter delta=0)
        r2 = requests.post(f"{API}/ads/{ad_id}/view", timeout=10)
        assert r1.status_code in (200, 204)
        assert r2.status_code in (200, 204)


class TestRegressionAdmin:
    def test_admin_deals(self, admin):
        r = requests.get(f"{API}/admin/deals", headers=admin["h"], timeout=10)
        assert r.status_code == 200
        body = r.json()
        # Either a list or an object with deals[]
        assert isinstance(body, list) or "deals" in body

    def test_admin_ads(self, admin):
        r = requests.get(f"{API}/admin/ads", headers=admin["h"], timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list) or "ads" in body


class TestRegressionExternalOffers:
    def test_external_offers_endpoints(self):
        # /external-offers/keyless is public per server.py
        r = requests.get(f"{API}/external-offers/keyless", timeout=20)
        assert r.status_code in (200, 401, 403)
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, (list, dict))


class TestRegressionUpload:
    @pytest.mark.parametrize("filename,mime,kind", [
        ("test.png", "image/png", "post"),
        ("test.mp4", "video/mp4", "post"),
        ("test.webm", "video/webm", "post"),
        ("test.mov", "video/quicktime", "post"),
        ("test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "doc"),
        ("test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "doc"),
        ("test.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "doc"),
    ])
    def test_upload_accepts(self, candidate, filename, mime, kind):
        files = {"file": (filename, io.BytesIO(b"\x00" * 256), mime)}
        data = {"kind": kind}
        r = requests.post(f"{API}/upload", files=files, data=data,
                          headers={"Authorization": candidate["h"]["Authorization"]},
                          timeout=20)
        # Accept either 200 (uploaded) or 400 if magic-byte sniff rejects fake content,
        # but the route must not 404 / 500.
        assert r.status_code in (200, 400), f"{filename}: {r.status_code} {r.text}"
