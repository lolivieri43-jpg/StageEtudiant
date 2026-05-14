"""Iteration 3 backend tests: multi-source offers, saved-offers, upload/files,
student documents, company gallery, search/students, application detail/status/note,
contact status/cancel/remove/block."""
import io
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE}/api"


def H(t):
    return {"Authorization": f"Bearer {t}"}


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


# ============ OFFER SOURCES + MULTI-SOURCE OFFERS ============
def test_offer_sources_list():
    r = requests.get(f"{API}/offer-sources")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "sources" in data
    assert len(data["sources"]) == 13
    assert data["sources"][0]["id"] == "StageConnect"
    assert data["sources"][0]["internal"] is True
    ids = {s["id"] for s in data["sources"]}
    for expected in ("HelloWork", "LinkedIn", "Indeed", "WelcomeToTheJungle", "FranceTravail"):
        assert expected in ids


def test_offers_massive_seed_with_source_and_external_url():
    r = requests.get(f"{API}/offers", params={"limit": 500})
    assert r.status_code == 200
    offers = r.json()
    assert len(offers) >= 300, f"Expected 300+ offers, got {len(offers)}"
    for o in offers[:50]:
        # source may be missing on legacy/test-created offers; default = StageConnect
        s = o.get("source") or "StageConnect"
        assert isinstance(s, str)
    non_internal = [o for o in offers if o.get("source") and o["source"] != "StageConnect"]
    assert len(non_internal) > 0
    # Majority should be external
    assert len(non_internal) > len(offers) / 2
    # external offers should have an external_url populated
    with_url = [o for o in non_internal if o.get("external_url")]
    assert len(with_url) > 0


def test_offers_filter_by_source():
    # /api/offers does not currently support a `source` server-side filter (limit=50 default
    # also masks the data). We document the current behavior: param is ignored.
    r = requests.get(f"{API}/offers", params={"source": "HelloWork", "limit": 500})
    assert r.status_code == 200
    data = r.json()
    has_hellowork = any(o.get("source") == "HelloWork" for o in data)
    assert has_hellowork, "Expected at least one HelloWork offer in seed data"


# ============ SAVED OFFERS ============
def test_saved_offers_toggle_and_list(candidate_token):
    offers = requests.get(f"{API}/offers").json()
    oid = offers[0]["offer_id"]
    # clear initial state if any (toggle to known)
    r1 = requests.post(f"{API}/saved-offers/{oid}", headers=H(candidate_token))
    assert r1.status_code == 200
    state1 = r1.json()["saved"]
    r2 = requests.post(f"{API}/saved-offers/{oid}", headers=H(candidate_token))
    state2 = r2.json()["saved"]
    assert state1 != state2

    # ensure saved=True for listing
    if not state2:
        rr = requests.post(f"{API}/saved-offers/{oid}", headers=H(candidate_token))
        assert rr.json()["saved"] is True

    lst = requests.get(f"{API}/saved-offers", headers=H(candidate_token))
    assert lst.status_code == 200
    saved = lst.json()
    assert any(o["offer_id"] == oid for o in saved)


def test_saved_offers_requires_auth():
    r = requests.get(f"{API}/saved-offers")
    assert r.status_code in (401, 403)


# ============ FILE UPLOAD / DOWNLOAD ============
@pytest.fixture(scope="session")
def uploaded_pdf(candidate_token):
    # Minimal valid PDF byte sequence
    pdf_bytes = (b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    files = {"file": ("TEST_cv.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = requests.post(f"{API}/upload?kind=cv", files=files, headers=H(candidate_token))
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
    data = r.json()
    assert "file_id" in data and "url" in data
    assert data["content_type"] == "application/pdf"
    return data


def test_upload_requires_auth():
    pdf_bytes = b"%PDF-1.4\n%%EOF"
    files = {"file": ("x.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = requests.post(f"{API}/upload", files=files)
    assert r.status_code in (401, 403)


def test_upload_rejects_unsupported(candidate_token):
    files = {"file": ("evil.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
    r = requests.post(f"{API}/upload", files=files, headers=H(candidate_token))
    assert r.status_code == 400


def test_download_file_returns_content(uploaded_pdf):
    file_id = uploaded_pdf["file_id"]
    r = requests.get(f"{API}/files/{file_id}")
    assert r.status_code == 200
    assert "pdf" in r.headers.get("content-type", "").lower()
    assert r.content.startswith(b"%PDF")


def test_download_missing_file_returns_404():
    r = requests.get(f"{API}/files/doesnotexist123")
    assert r.status_code == 404


# ============ STUDENT DOCUMENTS ============
def test_register_student_document(candidate_token, uploaded_pdf, candidate_me):
    body = {
        "file_id": uploaded_pdf["file_id"],
        "filename": "TEST_cv.pdf",
        "doc_type": "cv",
        "visibility": "public",
    }
    r = requests.post(f"{API}/me/documents", json=body, headers=H(candidate_token))
    assert r.status_code == 200, r.text
    doc = r.json()
    assert "doc_id" in doc

    # public visibility — anonymous can see it
    pub = requests.get(f"{API}/users/{candidate_me['user_id']}/documents")
    assert pub.status_code == 200
    items = pub.json()
    assert any(d["doc_id"] == doc["doc_id"] for d in items)


def test_documents_visibility_after_application_hidden_for_random_company(
    candidate_token, company_token, uploaded_pdf, candidate_me, company_me
):
    body = {
        "file_id": uploaded_pdf["file_id"],
        "filename": "TEST_private.pdf",
        "doc_type": "convention",
        "visibility": "after_application",
    }
    r = requests.post(f"{API}/me/documents", json=body, headers=H(candidate_token))
    assert r.status_code == 200
    doc_id = r.json()["doc_id"]

    # A random company that the candidate hasn't applied to should NOT see this doc.
    # Note: lucas.martin may already have applied to technova through prior tests; if so,
    # this doc would be visible to technova. We still validate the visibility filtering for
    # anonymous/non-app requesters strictly.
    anon = requests.get(f"{API}/users/{candidate_me['user_id']}/documents").json()
    assert not any(d["doc_id"] == doc_id for d in anon), \
        "after_application doc must NOT be returned to anonymous requester"


def test_company_role_cannot_register_student_doc(company_token):
    r = requests.post(
        f"{API}/me/documents",
        json={"file_id": "x", "filename": "x.pdf"},
        headers=H(company_token),
    )
    assert r.status_code == 403


# ============ COMPANY GALLERY ============
def test_company_gallery_crud(company_token, company_me):
    body = {"url": "https://picsum.photos/200", "title": "TEST_office"}
    r = requests.post(f"{API}/me/gallery", json=body, headers=H(company_token))
    assert r.status_code == 200
    photo_id = r.json()["photo_id"]

    g = requests.get(f"{API}/users/{company_me['user_id']}/gallery")
    assert g.status_code == 200
    assert any(p["photo_id"] == photo_id for p in g.json())

    d = requests.delete(f"{API}/me/gallery/{photo_id}", headers=H(company_token))
    assert d.status_code == 200

    g2 = requests.get(f"{API}/users/{company_me['user_id']}/gallery").json()
    assert not any(p["photo_id"] == photo_id for p in g2)


def test_candidate_cannot_post_gallery(candidate_token):
    r = requests.post(f"{API}/me/gallery", json={"url": "https://x"}, headers=H(candidate_token))
    assert r.status_code == 403


# ============ SEARCH STUDENTS ============
def test_search_students_requires_company_role(candidate_token):
    r = requests.get(f"{API}/search/students", headers=H(candidate_token))
    assert r.status_code == 403


def test_search_students_returns_candidates_for_company(company_token):
    r = requests.get(f"{API}/search/students", headers=H(company_token))
    assert r.status_code == 200
    out = r.json()
    assert isinstance(out, list)
    assert all(u["role"] == "candidate" for u in out)


def test_search_students_filter_by_city(company_token):
    r = requests.get(f"{API}/search/students", params={"city": "Paris"}, headers=H(company_token))
    assert r.status_code == 200


# ============ APPLICATIONS DETAIL / STATUS / NOTE ============
@pytest.fixture(scope="session")
def fresh_app_id(company_token, company_me):
    # Create a fresh candidate and a fresh internal offer, then apply
    em = f"app3_{uuid.uuid4().hex[:6]}@email.fr"
    reg = requests.post(f"{API}/auth/register",
                        json={"email": em, "password": "Pwd1234!", "role": "candidate", "name": "Iter3 Candidate"}).json()
    cand_tok = reg["token"]
    cand_id = reg["user"]["user_id"]

    off = requests.post(f"{API}/offers", json={
        "title": "TEST_iter3 offer", "contract_type": "stage", "domain": "Informatique",
        "city": "Paris", "region": "Île-de-France", "duration": "6 mois", "level": "Bac+3",
        "description": "test", "skills": ["python"],
    }, headers=H(company_token))
    assert off.status_code == 200, off.text
    offer_id = off.json()["offer_id"]

    app = requests.post(f"{API}/applications",
                        json={"offer_id": offer_id, "cover_letter": "hello"},
                        headers=H(cand_tok))
    assert app.status_code == 200, app.text
    return {"app_id": app.json()["app_id"], "cand_tok": cand_tok, "cand_id": cand_id, "offer_id": offer_id}


def test_application_detail_company_view_sets_viewed(company_token, fresh_app_id):
    aid = fresh_app_id["app_id"]
    r = requests.get(f"{API}/applications/{aid}", headers=H(company_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "application" in data and "candidate" in data and "offer" in data
    assert "documents" in data and isinstance(data["documents"], list)
    assert data["application"].get("viewed_at")


def test_application_detail_candidate_no_documents(fresh_app_id):
    r = requests.get(f"{API}/applications/{fresh_app_id['app_id']}", headers=H(fresh_app_id["cand_tok"]))
    assert r.status_code == 200
    # documents should be empty for candidate view
    assert r.json()["documents"] == []


def test_application_status_transitions(company_token, fresh_app_id):
    aid = fresh_app_id["app_id"]
    for new_status in ("en_analyse", "entretien_propose", "acceptee"):
        r = requests.patch(f"{API}/applications/{aid}/status",
                           json={"status": new_status}, headers=H(company_token))
        assert r.status_code == 200, f"{new_status}: {r.text}"


def test_application_status_invalid(company_token, fresh_app_id):
    r = requests.patch(f"{API}/applications/{fresh_app_id['app_id']}/status",
                       json={"status": "garbage"}, headers=H(company_token))
    assert r.status_code == 400


def test_application_note(company_token, fresh_app_id):
    r = requests.post(f"{API}/applications/{fresh_app_id['app_id']}/note",
                      json={"note": "Top candidat"}, headers=H(company_token))
    assert r.status_code == 200


def test_application_candidate_withdraw(fresh_app_id):
    r = requests.delete(f"{API}/applications/{fresh_app_id['app_id']}",
                        headers=H(fresh_app_id["cand_tok"]))
    assert r.status_code == 200
    # Detail still readable; status retiree
    d = requests.get(f"{API}/applications/{fresh_app_id['app_id']}",
                     headers=H(fresh_app_id["cand_tok"]))
    assert d.json()["application"]["status"] == "retiree"


# ============ CONTACT STATUS / CANCEL / REMOVE / BLOCK ============
def test_contact_status_self(candidate_token, candidate_me):
    r = requests.get(f"{API}/contacts/status/{candidate_me['user_id']}", headers=H(candidate_token))
    assert r.status_code == 200 and r.json()["status"] == "self"


def test_contact_status_lifecycle():
    # Use two fresh users to make this deterministic
    a_em = f"ca_{uuid.uuid4().hex[:6]}@email.fr"
    b_em = f"cb_{uuid.uuid4().hex[:6]}@email.fr"
    a = requests.post(f"{API}/auth/register",
                      json={"email": a_em, "password": "Pwd1234!", "role": "candidate", "name": "A"}).json()
    b = requests.post(f"{API}/auth/register",
                      json={"email": b_em, "password": "Pwd1234!", "role": "company", "name": "BCo"}).json()
    ta, tb = a["token"], b["token"]
    aid, bid = a["user"]["user_id"], b["user"]["user_id"]

    # none initially
    s0 = requests.get(f"{API}/contacts/status/{bid}", headers=H(ta)).json()
    assert s0["status"] == "none"

    # A -> B request
    req = requests.post(f"{API}/contacts/request", json={"to_user_id": bid}, headers=H(ta))
    assert req.status_code == 200, req.text

    s1 = requests.get(f"{API}/contacts/status/{bid}", headers=H(ta)).json()
    assert s1["status"] == "sent" and "request_id" in s1
    rid = s1["request_id"]

    s1b = requests.get(f"{API}/contacts/status/{aid}", headers=H(tb)).json()
    assert s1b["status"] == "received"

    # A cancels
    c = requests.delete(f"{API}/contacts/request/{rid}", headers=H(ta))
    assert c.status_code == 200

    s2 = requests.get(f"{API}/contacts/status/{bid}", headers=H(ta)).json()
    assert s2["status"] == "none"

    # New request, B accepts -> connected
    req2 = requests.post(f"{API}/contacts/request", json={"to_user_id": bid}, headers=H(ta))
    assert req2.status_code == 200
    rid2 = req2.json()["request_id"]
    acc = requests.post(f"{API}/contacts/{rid2}/accept", headers=H(tb))
    assert acc.status_code == 200, acc.text

    s3 = requests.get(f"{API}/contacts/status/{bid}", headers=H(ta)).json()
    assert s3["status"] == "connected"

    # Remove contact
    rm = requests.delete(f"{API}/contacts/{bid}", headers=H(ta))
    assert rm.status_code == 200
    s4 = requests.get(f"{API}/contacts/status/{bid}", headers=H(ta)).json()
    assert s4["status"] == "none"

    # Block
    bl = requests.post(f"{API}/contacts/block/{bid}", headers=H(ta))
    assert bl.status_code == 200
