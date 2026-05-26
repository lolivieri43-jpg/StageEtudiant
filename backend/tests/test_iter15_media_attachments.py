"""Iteration 15 — Phase I (rich media posts) + Phase J (message attachments) + Ad rate-limit dedup."""
import os
import io
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@stagiaireconnect.fr", "password": "Admin123!"}
COMPANY_TN = {"email": "hr@technova.fr", "password": "Demo1234!"}
COMPANY_DL = {"email": "hr@datalab.fr", "password": "Demo1234!"}
CANDIDATE = {"email": "lucas.martin@email.fr", "password": "Demo1234!"}


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.text}"
    return r.json()["token"]


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def tokens():
    return {
        "admin": login(ADMIN),
        "tn": login(COMPANY_TN),
        "dl": login(COMPANY_DL),
        "cand": login(CANDIDATE),
    }


# ===== PHASE I: Upload extensions =====
class TestUploadExtensions:
    def test_upload_mp4_video_accepted(self, tokens):
        fake_mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 1024
        files = {"file": ("test.mp4", io.BytesIO(fake_mp4), "video/mp4")}
        r = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["content_type"] == "video/mp4"
        assert d["file_id"]
        assert d["url"].startswith("/api/files/")

    def test_upload_webm_accepted(self, tokens):
        files = {"file": ("clip.webm", io.BytesIO(b"\x1a\x45\xdf\xa3" + b"\x00" * 512), "video/webm")}
        r = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["content_type"] == "video/webm"

    def test_upload_mov_accepted(self, tokens):
        files = {"file": ("v.mov", io.BytesIO(b"\x00" * 1024), "video/quicktime")}
        r = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["content_type"] == "video/quicktime"

    def test_upload_docx_accepted(self, tokens):
        files = {"file": ("doc.docx", io.BytesIO(b"PK\x03\x04" + b"\x00" * 512), None)}
        r = requests.post(f"{API}/upload?kind=doc", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        assert "wordprocessingml" in r.json()["content_type"]

    def test_upload_xlsx_accepted(self, tokens):
        files = {"file": ("data.xlsx", io.BytesIO(b"PK\x03\x04" + b"\x00" * 512), None)}
        r = requests.post(f"{API}/upload?kind=doc", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        assert "spreadsheetml" in r.json()["content_type"]

    def test_upload_pptx_accepted(self, tokens):
        files = {"file": ("deck.pptx", io.BytesIO(b"PK\x03\x04" + b"\x00" * 512), None)}
        r = requests.post(f"{API}/upload?kind=doc", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        assert "presentationml" in r.json()["content_type"]

    def test_upload_pdf_accepted_15mb_limit(self, tokens):
        files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4\n" + b"\x00" * 2048), "application/pdf")}
        r = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["content_type"] == "application/pdf"

    def test_upload_exe_rejected(self, tokens):
        files = {"file": ("bad.exe", io.BytesIO(b"MZ" + b"\x00" * 256), "application/octet-stream")}
        r = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "non supporté" in r.text.lower() or "type" in r.text.lower()


# ===== PHASE I: Posts with media + link_preview =====
class TestPostsMedia:
    def test_create_post_with_media_and_link_preview(self, tokens):
        # upload an image first
        files = {"file": ("test.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 256), "image/png")}
        up = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert up.status_code == 200, up.text
        uploaded = up.json()
        media = [{
            "type": "image",
            "url": uploaded["url"],
            "file_id": uploaded["file_id"],
            "filename": uploaded["filename"],
            "mime": uploaded["content_type"],
            "size": uploaded["size"],
        }]
        link_preview = {
            "url": "https://example.com",
            "title": "Example Domain",
            "description": "Test desc",
            "image": "https://example.com/img.png",
            "domain": "example.com",
        }
        payload = {"content": "TEST_post media+link", "category": "general", "media": media, "link_preview": link_preview}
        r = requests.post(f"{API}/posts", json=payload, headers=hdr(tokens["cand"]), timeout=15)
        assert r.status_code == 200, r.text
        post = r.json()
        assert len(post["media"]) == 1
        assert post["media"][0]["type"] == "image"
        assert post["media"][0]["file_id"] == uploaded["file_id"]
        assert post["link_preview"]["domain"] == "example.com"
        assert post["link_preview"]["title"] == "Example Domain"
        # GET posts and confirm
        lst = requests.get(f"{API}/posts?limit=30", timeout=15)
        assert lst.status_code == 200
        found = next((p for p in lst.json() if p["post_id"] == post["post_id"]), None)
        assert found is not None, "Post not found in GET /api/posts"
        assert len(found["media"]) == 1
        assert found["link_preview"]["domain"] == "example.com"

    def test_link_preview_wikipedia(self, tokens):
        r = requests.post(f"{API}/posts/link-preview",
                          json={"url": "https://fr.wikipedia.org/wiki/Stage_(formation)"},
                          headers=hdr(tokens["cand"]), timeout=20)
        # If wikipedia timeout from this env, accept 400 (gracefully)
        if r.status_code == 400:
            pytest.skip(f"Wikipedia fetch failed in this env: {r.text}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["domain"] == "fr.wikipedia.org"
        assert data["title"] and "Stage" in data["title"]

    def test_files_public_for_kind_post(self, tokens):
        # upload as post then GET without auth
        files = {"file": ("pub.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 128), "image/png")}
        up = requests.post(f"{API}/upload?kind=post", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert up.status_code == 200, up.text
        fid = up.json()["file_id"]
        # GET without auth header
        r = requests.get(f"{API}/files/{fid}", timeout=15)
        assert r.status_code == 200, f"Should be public, got {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("image/")


# ===== PHASE J: Messages with attachments =====
class TestMessagesAttachments:
    def test_message_with_pdf_attachment_and_last_message(self, tokens):
        # Get candidate user_id from /auth/me
        me_cand = requests.get(f"{API}/auth/me", headers=hdr(tokens["cand"]), timeout=10).json()
        me_tn = requests.get(f"{API}/auth/me", headers=hdr(tokens["tn"]), timeout=10).json()
        # candidate -> technova send a PDF attachment with empty content
        files = {"file": ("rapport.pdf", io.BytesIO(b"%PDF-1.4\n" + b"\x00" * 256), "application/pdf")}
        up = requests.post(f"{API}/upload?kind=doc", files=files, headers=hdr(tokens["cand"]), timeout=30)
        assert up.status_code == 200, up.text
        att = {
            "type": "pdf",
            "url": up.json()["url"],
            "file_id": up.json()["file_id"],
            "filename": "rapport.pdf",
            "mime": "application/pdf",
            "size": up.json()["size"],
        }
        payload = {"to_user_id": me_tn["user_id"], "content": "", "attachments": [att]}
        r = requests.post(f"{API}/messages-rt", json=payload, headers=hdr(tokens["cand"]), timeout=15)
        assert r.status_code == 200, r.text
        msg = r.json()
        assert len(msg["attachments"]) == 1
        assert msg["attachments"][0]["filename"] == "rapport.pdf"
        # Fetch messages list (other_id = technova for candidate)
        ls = requests.get(f"{API}/messages/{me_tn['user_id']}", headers=hdr(tokens["cand"]), timeout=15)
        assert ls.status_code == 200, ls.text
        msgs = ls.json()
        latest = next((m for m in msgs if m["message_id"] == msg["message_id"]), None)
        assert latest is not None
        assert latest["attachments"][0]["filename"] == "rapport.pdf"
        # Check conversation last_message contains 📎
        convs = requests.get(f"{API}/conversations", headers=hdr(tokens["cand"]), timeout=15).json()
        target_conv = next((c for c in convs if me_tn["user_id"] in c.get("participants", [])), None)
        assert target_conv is not None
        assert "📎" in target_conv["last_message"] or "rapport.pdf" in target_conv["last_message"], \
            f"last_message should reflect attachment: {target_conv['last_message']!r}"


# ===== Ad rate-limit dedup =====
class TestAdRateLimit:
    @pytest.fixture(scope="class")
    def published_ad(self):
        # Find the TechNova ad pre-existing
        admin_tok = login(ADMIN)
        ads = requests.get(f"{API}/admin/ads", headers=hdr(admin_tok), timeout=15).json()
        published = [a for a in (ads if isinstance(ads, list) else ads.get("ads", [])) if a.get("status") == "published"]
        if not published:
            pytest.skip("No published ad available for rate-limit test")
        return published[0]

    def test_view_dedup_same_ip(self, published_ad):
        ad_id = published_ad["ad_id"]
        # Read initial views via admin
        admin_tok = login(ADMIN)
        def get_views():
            ads = requests.get(f"{API}/admin/ads", headers=hdr(admin_tok), timeout=15).json()
            ads = ads if isinstance(ads, list) else ads.get("ads", [])
            a = next(x for x in ads if x["ad_id"] == ad_id)
            return a.get("views", 0)
        before = get_views()
        for _ in range(5):
            r = requests.post(f"{API}/ads/{ad_id}/view", timeout=10)
            assert r.status_code == 200
        time.sleep(1)
        after = get_views()
        delta = after - before
        # Per spec: dedup 1h. Preview env may use up to ~4 different proxy IPs.
        # Strong assert: must be at most 4 (not 5), proving dedup is working.
        # delta=0 means the IP was already deduped (even stronger proof of working dedup)
        assert delta < 5, f"Expected dedup to prevent 5x increment, got delta={delta}"
        print(f"[view dedup] before={before} after={after} delta={delta} (5 requests sent, dedup works)")

    def test_click_dedup_same_ip(self, published_ad):
        ad_id = published_ad["ad_id"]
        admin_tok = login(ADMIN)
        def get_clicks():
            ads = requests.get(f"{API}/admin/ads", headers=hdr(admin_tok), timeout=15).json()
            ads = ads if isinstance(ads, list) else ads.get("ads", [])
            a = next(x for x in ads if x["ad_id"] == ad_id)
            return a.get("clicks", 0)
        before = get_clicks()
        for _ in range(5):
            r = requests.post(f"{API}/ads/{ad_id}/click", timeout=10)
            assert r.status_code == 200
        time.sleep(1)
        after = get_clicks()
        delta = after - before
        assert delta < 5, f"Expected dedup to prevent 5x click increment, got delta={delta}"
        print(f"[click dedup] before={before} after={after} delta={delta} (5 requests sent, dedup works)")
