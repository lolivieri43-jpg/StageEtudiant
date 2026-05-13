"""Backend tests for StagiaireConnect."""
import os, uuid, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email":"admin@stagiaireconnect.fr","password":"Admin123!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="session")
def company_token():
    r = requests.post(f"{API}/auth/login", json={"email":"hr@technova.fr","password":"Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="session")
def candidate_token():
    r = requests.post(f"{API}/auth/login", json={"email":"lucas.martin@email.fr","password":"Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]

def H(t): return {"Authorization": f"Bearer {t}"}

# Auth
def test_root():
    assert requests.get(f"{API}/").status_code == 200

def test_register_and_me():
    em = f"test_{uuid.uuid4().hex[:8]}@email.fr"
    r = requests.post(f"{API}/auth/register", json={"email":em,"password":"Pwd1234!","role":"candidate","name":"Test User"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    me = requests.get(f"{API}/auth/me", headers=H(tok))
    assert me.status_code == 200 and me.json()["email"] == em

def test_login_invalid():
    r = requests.post(f"{API}/auth/login", json={"email":"bad@x.fr","password":"x"})
    assert r.status_code == 401

# Offers
def test_offers_list_and_filters():
    r = requests.get(f"{API}/offers")
    assert r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 1
    r2 = requests.get(f"{API}/offers", params={"contract_type":"stage"})
    assert r2.status_code == 200
    assert all(o["contract_type"]=="stage" for o in r2.json())

def test_offers_regions_route_order():
    r = requests.get(f"{API}/offers/regions")
    assert r.status_code == 200, r.text
    assert "by_region" in r.json()

def test_offer_detail_views_increment():
    offers = requests.get(f"{API}/offers").json()
    oid = offers[0]["offer_id"]
    v1 = requests.get(f"{API}/offers/{oid}").json()["views"]
    v2 = requests.get(f"{API}/offers/{oid}").json()["views"]
    assert v2 == v1 + 1

def test_create_offer_company(company_token):
    payload = {"title":"TEST_Stage QA","contract_type":"stage","domain":"Informatique","city":"Paris","region":"Île-de-France","duration":"6 mois","level":"Bac+3","description":"Test offre","skills":["QA"]}
    r = requests.post(f"{API}/offers", json=payload, headers=H(company_token))
    assert r.status_code == 200, r.text
    oid = r.json()["offer_id"]
    g = requests.get(f"{API}/offers/{oid}")
    assert g.status_code == 200 and g.json()["title"] == "TEST_Stage QA"

def test_create_offer_forbidden_for_candidate(candidate_token):
    r = requests.post(f"{API}/offers", json={"title":"x","contract_type":"stage","domain":"x","city":"x","region":"x","duration":"x","level":"x","description":"x"}, headers=H(candidate_token))
    assert r.status_code == 403

# Applications
def test_application_flow(candidate_token, company_token):
    offers = requests.get(f"{API}/offers", params={"company_id":""}).json()
    # find offer not already applied; create fresh user for clean state
    em = f"app_{uuid.uuid4().hex[:6]}@email.fr"
    reg = requests.post(f"{API}/auth/register", json={"email":em,"password":"Pwd1234!","role":"candidate","name":"Apply Test"}).json()
    tok = reg["token"]
    oid = offers[0]["offer_id"]
    r = requests.post(f"{API}/applications", json={"offer_id":oid,"cover_letter":"hi"}, headers=H(tok))
    assert r.status_code == 200, r.text
    app_id = r.json()["app_id"]
    # duplicate
    r2 = requests.post(f"{API}/applications", json={"offer_id":oid}, headers=H(tok))
    assert r2.status_code == 400
    # company updates status
    upd = requests.patch(f"{API}/applications/{app_id}", json={"status":"vue"}, headers=H(company_token))
    assert upd.status_code == 200

# Posts
def test_posts_like_comment(candidate_token):
    r = requests.post(f"{API}/posts", json={"content":"TEST_post","category":"general"}, headers=H(candidate_token))
    assert r.status_code == 200
    pid = r.json()["post_id"]
    lst = requests.get(f"{API}/posts").json()
    assert any(p["post_id"]==pid for p in lst)
    lk = requests.post(f"{API}/posts/{pid}/like", headers=H(candidate_token))
    assert lk.status_code == 200 and len(lk.json()["likes"]) == 1
    lk2 = requests.post(f"{API}/posts/{pid}/like", headers=H(candidate_token))
    assert len(lk2.json()["likes"]) == 0
    c = requests.post(f"{API}/posts/comment", json={"post_id":pid,"content":"nice"}, headers=H(candidate_token))
    assert c.status_code == 200

# Messages
def test_messages_and_conversations(candidate_token, company_token):
    me_c = requests.get(f"{API}/auth/me", headers=H(company_token)).json()
    r = requests.post(f"{API}/messages", json={"to_user_id":me_c["user_id"],"content":"hello"}, headers=H(candidate_token))
    assert r.status_code == 200
    convs = requests.get(f"{API}/conversations", headers=H(candidate_token))
    assert convs.status_code == 200 and len(convs.json()) >= 1
    msgs = requests.get(f"{API}/messages/{me_c['user_id']}", headers=H(candidate_token))
    assert msgs.status_code == 200 and len(msgs.json()) >= 1

# Contacts
def test_contacts_request_accept(candidate_token, company_token):
    me_co = requests.get(f"{API}/auth/me", headers=H(company_token)).json()
    r = requests.post(f"{API}/contacts/request", json={"to_user_id":me_co["user_id"]}, headers=H(candidate_token))
    assert r.status_code in (200, 400)  # may already exist
    lst = requests.get(f"{API}/contacts", headers=H(company_token)).json()
    # try accepting first pending
    if lst.get("pending"):
        rid = lst["pending"][0]["request_id"]
        a = requests.post(f"{API}/contacts/{rid}/accept", headers=H(company_token))
        assert a.status_code == 200

# Notifications
def test_notifications(candidate_token):
    r = requests.get(f"{API}/notifications", headers=H(candidate_token))
    assert r.status_code == 200 and "notifications" in r.json()
    rd = requests.post(f"{API}/notifications/read", headers=H(candidate_token))
    assert rd.status_code == 200

# Dashboard
def test_dashboard_company(company_token):
    r = requests.get(f"{API}/dashboard", headers=H(company_token))
    assert r.status_code == 200 and "offers_count" in r.json()

def test_dashboard_candidate(candidate_token):
    r = requests.get(f"{API}/dashboard", headers=H(candidate_token))
    assert r.status_code == 200 and "applications_count" in r.json()

# Profile
def test_profile_update(candidate_token):
    r = requests.put(f"{API}/profile", json={"city":"Paris","title":"QA Tester"}, headers=H(candidate_token))
    assert r.status_code == 200
    me = requests.get(f"{API}/auth/me", headers=H(candidate_token)).json()
    assert me["profile"]["city"] == "Paris"

def test_user_public():
    offers = requests.get(f"{API}/offers").json()
    uid = offers[0]["company_id"]
    r = requests.get(f"{API}/users/{uid}")
    assert r.status_code == 200 and "password" not in r.json()

# Admin
def test_admin_stats(admin_token, candidate_token):
    r = requests.get(f"{API}/admin/stats", headers=H(admin_token))
    assert r.status_code == 200 and r.json()["users"] > 0
    forbidden = requests.get(f"{API}/admin/stats", headers=H(candidate_token))
    assert forbidden.status_code == 403

def test_admin_users(admin_token):
    r = requests.get(f"{API}/admin/users", headers=H(admin_token))
    assert r.status_code == 200 and len(r.json()) > 0

def test_admin_verify(admin_token):
    co = requests.get(f"{API}/users", params={"role":"company"}).json()[0]
    r = requests.post(f"{API}/admin/verify/{co['user_id']}", headers=H(admin_token))
    assert r.status_code == 200

def test_auth_session_endpoint_exists():
    # signature exists; invalid session id should fail
    r = requests.post(f"{API}/auth/session", json={"session_id":"invalid"})
    assert r.status_code in (401, 500)
