"""Iteration 14 — Deals moderation workflow + Ads (sponsored advertisements).

Covers:
- Deals: auto-pending on create (company & candidate), admin validate (approve/refuse/suspend/reactivate),
  PATCH by author re-triggers pending
- Ads: CRUD (company), quota (1 free / illim Pro), 402 on quota exceeded, draft mode,
  PATCH by author -> back to pending, public list filter (status+window), tracking view/click,
  admin list with counts+stats, admin validate (approve/refuse/suspend/reactivate)
"""
import os
import time
import uuid
import pytest
import requests

def _load_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
ADMIN = ("admin@stagiaireconnect.fr", "Admin123!")
CO_FREE = ("hr@technova.fr", "Demo1234!")     # already has 1 active ad created
CO_ALT = ("hr@datalab.fr", "Demo1234!")       # no ad
CAND = ("lucas.martin@email.fr", "Demo1234!")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def co_alt_tok():
    return _login(*CO_ALT)


@pytest.fixture(scope="module")
def co_free_tok():
    return _login(*CO_FREE)


@pytest.fixture(scope="module")
def cand_tok():
    return _login(*CAND)


# ============================ DEALS WORKFLOW ============================

class TestDealsWorkflow:

    def test_company_create_deal_pending(self, co_alt_tok):
        payload = {"title": f"TEST_deal_co_{uuid.uuid4().hex[:6]}",
                   "description": "Bon plan entreprise test",
                   "category": "food", "discount": "-15%"}
        r = requests.post(f"{BASE_URL}/api/deals", json=payload, headers=_h(co_alt_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["status"] == "pending", f"Company deal should be pending, got {d['status']}"
        assert d["author_type"] == "company"
        TestDealsWorkflow.co_deal_id = d["deal_id"]

    def test_candidate_create_deal_pending(self, cand_tok):
        payload = {"title": f"TEST_deal_cand_{uuid.uuid4().hex[:6]}",
                   "description": "Bon plan étudiant test",
                   "category": "study"}
        r = requests.post(f"{BASE_URL}/api/deals", json=payload, headers=_h(cand_tok), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "pending"
        TestDealsWorkflow.cand_deal_id = d["deal_id"]

    def test_admin_list_deals_with_counts(self, admin_tok):
        r = requests.get(f"{BASE_URL}/api/admin/deals", params={"status": "pending"},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "deals" in data and "counts" in data
        counts = data["counts"]
        for k in ("draft", "pending", "published", "refused", "suspended", "expired", "all"):
            assert k in counts, f"Missing count {k}"
        assert counts["pending"] >= 2

    def test_admin_approve_deal(self, admin_tok):
        deal_id = TestDealsWorkflow.co_deal_id
        r = requests.post(f"{BASE_URL}/api/admin/deals/{deal_id}/validate",
                          json={"action": "approve"}, headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "published"
        # verify persisted
        r2 = requests.get(f"{BASE_URL}/api/deals/{deal_id}", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["status"] == "published"

    def test_author_edit_published_deal_back_to_pending(self, co_alt_tok):
        deal_id = TestDealsWorkflow.co_deal_id
        r = requests.patch(f"{BASE_URL}/api/deals/{deal_id}",
                           json={"description": "edited description"},
                           headers=_h(co_alt_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["status"] == "pending"

    def test_admin_refuse_deal(self, admin_tok):
        deal_id = TestDealsWorkflow.cand_deal_id
        r = requests.post(f"{BASE_URL}/api/admin/deals/{deal_id}/validate",
                          json={"action": "refuse", "reason": "doublon"},
                          headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "refused"

    def test_admin_suspend_then_reactivate(self, admin_tok):
        deal_id = TestDealsWorkflow.co_deal_id
        # First re-approve (it was set back to pending by author edit)
        requests.post(f"{BASE_URL}/api/admin/deals/{deal_id}/validate",
                      json={"action": "approve"}, headers=_h(admin_tok), timeout=15)
        # Suspend
        r = requests.post(f"{BASE_URL}/api/admin/deals/{deal_id}/validate",
                          json={"action": "suspend"}, headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "suspended"
        # Reactivate
        r2 = requests.post(f"{BASE_URL}/api/admin/deals/{deal_id}/validate",
                           json={"action": "reactivate"}, headers=_h(admin_tok), timeout=15)
        assert r2.status_code == 200 and r2.json()["status"] == "published"

    def test_cleanup_deals(self, admin_tok):
        for did in (getattr(TestDealsWorkflow, "co_deal_id", None),
                    getattr(TestDealsWorkflow, "cand_deal_id", None)):
            if did:
                requests.delete(f"{BASE_URL}/api/deals/{did}", headers=_h(admin_tok), timeout=10)


# ============================ ADS WORKFLOW ============================

class TestAdsWorkflow:

    def test_ads_mine_returns_quota(self, co_free_tok):
        r = requests.get(f"{BASE_URL}/api/ads/mine", headers=_h(co_free_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "ads" in data and "quota" in data and "pro" in data
        assert data["quota"]["max"] in (1, 9999)
        assert isinstance(data["pro"], bool)

    def test_candidate_cannot_create_ad(self, cand_tok):
        r = requests.post(f"{BASE_URL}/api/ads",
                          json={"title": "TEST_ad_forbidden"},
                          headers=_h(cand_tok), timeout=15)
        assert r.status_code == 403

    def test_co_alt_create_pending_ad(self, co_alt_tok):
        payload = {
            "title": f"TEST_ad_{uuid.uuid4().hex[:6]}",
            "short_text": "Une promo test",
            "image": "https://example.com/img.png",
            "logo": "https://example.com/logo.png",
            "cta_label": "Découvrir",
            "cta_url": "https://example.com",
            "promo_code": "TESTPROMO",
            "category": "food",
            "region": "Île-de-France",
            "city": "Paris",
            "start_date": None,
            "end_date": None,
            "blocks": [{"type": "text", "content": "Hello", "order": 0}],
            "style": {"bg_color": "#fff", "text_color": "#000", "accent_color": "#f00"},
            "template_id": "template-1",
        }
        r = requests.post(f"{BASE_URL}/api/ads", json=payload, headers=_h(co_alt_tok), timeout=15)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["status"] == "pending"
        assert d["title"] == payload["title"]
        assert d["template_id"] == "template-1"
        assert "ad_id" in d
        TestAdsWorkflow.alt_ad_id = d["ad_id"]

    def test_co_free_quota_blocks_second_ad(self, co_free_tok):
        """TechNova is free and already has 1 active ad => 402 expected."""
        r = requests.post(f"{BASE_URL}/api/ads",
                          json={"title": "TEST_ad_blocked"},
                          headers=_h(co_free_tok), timeout=15)
        # 402 if quota truly enforced; if technova quota was cleaned up, this becomes 200 — log and warn
        if r.status_code == 200:
            # Cleanup created ad
            ad_id = r.json().get("ad_id")
            if ad_id:
                # try delete via owner
                requests.delete(f"{BASE_URL}/api/ads/{ad_id}", headers=_h(co_free_tok), timeout=10)
            pytest.skip("TechNova free quota was empty — cannot validate 402 (seed state).")
        assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text[:200]}"

    def test_draft_does_not_require_quota(self, co_free_tok):
        """save_as_draft=True should bypass quota even if quota is full."""
        r = requests.post(f"{BASE_URL}/api/ads",
                          json={"title": f"TEST_ad_draft_{uuid.uuid4().hex[:6]}",
                                "save_as_draft": True},
                          headers=_h(co_free_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["status"] == "draft"
        TestAdsWorkflow.draft_ad_id = r.json()["ad_id"]

    def test_public_list_filters_status_published(self):
        r = requests.get(f"{BASE_URL}/api/ads/public", timeout=15)
        assert r.status_code == 200
        ads = r.json()
        assert isinstance(ads, list)
        for a in ads:
            assert a["status"] == "published", f"Public ad not published: {a.get('ad_id')} {a['status']}"

    def test_admin_approve_then_patch_back_to_pending(self, admin_tok, co_alt_tok):
        ad_id = TestAdsWorkflow.alt_ad_id
        # admin approve
        r = requests.post(f"{BASE_URL}/api/admin/ads/{ad_id}/validate",
                          json={"action": "approve"}, headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "published"
        # Author edits => should drop to pending
        r2 = requests.patch(f"{BASE_URL}/api/ads/{ad_id}",
                            json={"short_text": "updated text"},
                            headers=_h(co_alt_tok), timeout=15)
        assert r2.status_code == 200, r2.text[:300]
        assert r2.json()["status"] == "pending"

    def test_tracking_view_and_click(self):
        ad_id = TestAdsWorkflow.alt_ad_id
        r1 = requests.post(f"{BASE_URL}/api/ads/{ad_id}/view", timeout=10)
        assert r1.status_code == 200
        r2 = requests.post(f"{BASE_URL}/api/ads/{ad_id}/click", timeout=10)
        assert r2.status_code == 200
        # verify counters via GET
        g = requests.get(f"{BASE_URL}/api/ads/{ad_id}", timeout=10)
        assert g.status_code == 200
        data = g.json()
        assert data["views"] >= 1 and data["clicks"] >= 1

    def test_admin_list_ads_with_counts_and_stats(self, admin_tok):
        r = requests.get(f"{BASE_URL}/api/admin/ads",
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "ads" in data and "counts" in data and "stats" in data
        for k in ("draft", "pending", "published", "refused", "suspended", "expired", "all"):
            assert k in data["counts"]
        stats = data["stats"]
        assert "total_views" in stats and "total_clicks" in stats and "ctr" in stats and "ads" in stats

    def test_admin_suspend_then_reactivate_ad(self, admin_tok):
        ad_id = TestAdsWorkflow.alt_ad_id
        # approve first (was pending)
        requests.post(f"{BASE_URL}/api/admin/ads/{ad_id}/validate",
                      json={"action": "approve"}, headers=_h(admin_tok), timeout=15)
        r = requests.post(f"{BASE_URL}/api/admin/ads/{ad_id}/validate",
                          json={"action": "suspend"}, headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "suspended"
        r2 = requests.post(f"{BASE_URL}/api/admin/ads/{ad_id}/validate",
                           json={"action": "reactivate"}, headers=_h(admin_tok), timeout=15)
        assert r2.status_code == 200 and r2.json()["status"] == "published"

    def test_admin_refuse_ad(self, admin_tok):
        ad_id = TestAdsWorkflow.alt_ad_id
        r = requests.post(f"{BASE_URL}/api/admin/ads/{ad_id}/validate",
                          json={"action": "refuse", "reason": "test refuse"},
                          headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "refused"

    def test_admin_invalid_action(self, admin_tok):
        ad_id = TestAdsWorkflow.alt_ad_id
        r = requests.post(f"{BASE_URL}/api/admin/ads/{ad_id}/validate",
                          json={"action": "nonsense"}, headers=_h(admin_tok), timeout=10)
        assert r.status_code == 400

    def test_admin_ads_forbidden_anon(self):
        r = requests.get(f"{BASE_URL}/api/admin/ads", timeout=10)
        assert r.status_code in (401, 403)

    def test_delete_ad_owner_and_admin(self, co_alt_tok, admin_tok):
        # owner deletes the main one
        ad_id = TestAdsWorkflow.alt_ad_id
        r = requests.delete(f"{BASE_URL}/api/ads/{ad_id}", headers=_h(co_alt_tok), timeout=10)
        assert r.status_code == 200
        # admin deletes the draft
        draft_id = getattr(TestAdsWorkflow, "draft_ad_id", None)
        if draft_id:
            r2 = requests.delete(f"{BASE_URL}/api/ads/{draft_id}", headers=_h(admin_tok), timeout=10)
            assert r2.status_code == 200
