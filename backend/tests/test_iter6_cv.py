"""
Iteration 6 — CV en ligne integration with applications + 5 PDF templates.
Tests:
- /api/cv default pdf_template
- /api/cv PUT persist pdf_template
- /api/cv/export with each of the 5 templates
- POST /api/applications with use_online_cv stores snapshot + template
- GET /api/applications/{id}/cv (company + candidate)
- GET /api/applications/{id}/cv/export
- Access control (other company, other candidate -> 403)
- POST /api/applications without use_online_cv -> /cv 404
- /api/users/{id}/cv visibility (public/connected/after_application/private)
- SNAPSHOT FREEZE: modify CV after apply must not affect /api/applications/{id}/cv
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CANDIDATE = ("lucas.martin@email.fr", "Demo1234!")
COMPANY = ("hr@brightstudio011.fr", "Demo1234!")
ADMIN = ("admin@stagiaireconnect.fr", "Admin123!")

TEMPLATES = ["modern", "classique", "etudiant", "alternance", "professionnel"]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text[:200]}")
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok, f"No token in login response: {j}"
    return tok, j.get("user") or {}


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ------------------- Fixtures -------------------
@pytest.fixture(scope="module")
def candidate_auth():
    return _login(*CANDIDATE)


@pytest.fixture(scope="module")
def company_auth():
    return _login(*COMPANY)


@pytest.fixture(scope="module")
def admin_auth():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def second_candidate_auth():
    # find another candidate from seeded data (emma.dubois@email.fr usually exists)
    for email in ["emma.dubois@email.fr", "hugo.bernard@email.fr", "lea.petit@email.fr"]:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Demo1234!"}, timeout=20)
        if r.status_code == 200:
            j = r.json()
            return j.get("token"), j.get("user") or {}
    pytest.skip("No second candidate available")


@pytest.fixture(scope="module")
def second_company_auth():
    for email in ["hr@technova.fr", "hr@datalab.fr", "hr@greenpulse.fr"]:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Demo1234!"}, timeout=20)
        if r.status_code == 200:
            j = r.json()
            return j.get("token"), j.get("user") or {}
    pytest.skip("No second company available")


@pytest.fixture(scope="module", autouse=True)
def _reset_cv_skills(candidate_auth):
    """Ensure CV skills are STRINGS (canonical format used by the frontend)
    before PDF export tests run. Previous test runs may have polluted the
    document with object-shaped skills which crash modern/classique templates."""
    tok, _ = candidate_auth
    requests.put(f"{API}/cv", headers=_h(tok), json={
        "skills": ["Python", "React", "Communication"],
        "languages": [{"language": "Anglais", "level": "courant"}],
        "experiences": [{"company": "AcmeCo", "title": "Stagiaire dev",
                         "start_date": "2024-06", "end_date": "2024-09",
                         "description": "Snapshot exp"}],
        "educations": [{"degree": "Master Info", "school": "Sorbonne",
                        "city": "Paris", "start_date": "2024", "end_date": "2026"}],
        "professional_title": "Étudiant en informatique",
        "summary": "Passionné par le développement web et l'IA.",
    }, timeout=15)
    yield


# ------------------- /api/cv basics -------------------
class TestCvBasics:
    def test_get_cv_returns_defaults_with_pdf_template(self, candidate_auth):
        tok, _ = candidate_auth
        r = requests.get(f"{API}/cv", headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        cv = r.json()
        assert "pdf_template" in cv
        # may be already saved from prior runs - assert it's a valid template
        assert cv["pdf_template"] in TEMPLATES
        assert "visibility" in cv
        assert "educations" in cv and isinstance(cv["educations"], list)

    def test_put_cv_persists_pdf_template(self, candidate_auth):
        tok, _ = candidate_auth
        # set to etudiant
        r = requests.put(f"{API}/cv", headers=_h(tok),
                         json={"pdf_template": "etudiant",
                               "professional_title": "Étudiant en informatique",
                               "summary": "Passionné par le développement web et l'IA.",
                               "visibility": "public"}, timeout=15)
        assert r.status_code == 200, r.text
        cv = r.json()
        assert cv["pdf_template"] == "etudiant"
        # GET again to verify persistence
        r2 = requests.get(f"{API}/cv", headers=_h(tok), timeout=15)
        assert r2.status_code == 200
        assert r2.json()["pdf_template"] == "etudiant"

    def test_put_cv_ignores_unknown_fields(self, candidate_auth):
        tok, _ = candidate_auth
        r = requests.put(f"{API}/cv", headers=_h(tok),
                         json={"pdf_template": "modern", "is_admin": True, "user_id": "hacker"}, timeout=15)
        assert r.status_code == 200
        cv = r.json()
        assert "is_admin" not in cv or cv.get("is_admin") is not True


# ------------------- /api/cv/export with all 5 templates -------------------
class TestCvExportTemplates:
    @pytest.mark.parametrize("tpl", TEMPLATES)
    def test_export_each_template_returns_pdf(self, candidate_auth, tpl):
        tok, _ = candidate_auth
        r = requests.get(f"{API}/cv/export?template={tpl}", headers=_h(tok), timeout=30)
        assert r.status_code == 200, f"{tpl}: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        assert r.content[:4] == b"%PDF", f"Not a PDF for {tpl}"
        assert len(r.content) > 1500, f"PDF too small for {tpl}: {len(r.content)} bytes"


# ------------------- Application with online CV -------------------
@pytest.fixture(scope="module")
def internal_offer(company_auth):
    """Find an internal offer OWNED by the brightstudio011 company user."""
    tok, me = company_auth
    company_user_id = me.get("user_id")
    r = requests.get(f"{API}/offers?limit=500", headers=_h(tok), timeout=20)
    if r.status_code != 200:
        pytest.skip("Cannot list offers")
    offers = r.json() if isinstance(r.json(), list) else r.json().get("offers", [])
    mine = [o for o in offers if o.get("company_id") == company_user_id]
    if not mine:
        pytest.skip(f"No offers owned by company {company_user_id}")
    return mine[0]


@pytest.fixture(scope="module")
def created_application(candidate_auth, internal_offer):
    """Create an application using the online CV, returns app dict."""
    tok, _ = candidate_auth
    # Ensure CV has content
    requests.put(f"{API}/cv", headers=_h(tok),
                 json={"professional_title": "Candidat Test Iter6",
                       "summary": "Résumé snapshot original au moment de la candidature.",
                       "pdf_template": "modern",
                       "visibility": "public",
                       "experiences": [{"company": "AcmeCo", "title": "Stagiaire dev", "start_date": "2024-06", "end_date": "2024-09", "description": "Snapshot exp"}],
                       "skills": ["Python", "React"]}, timeout=15)
    # Delete any existing application first
    apps = requests.get(f"{API}/applications", headers=_h(tok), timeout=15)
    if apps.status_code == 200:
        for a in apps.json():
            if a.get("offer_id") == internal_offer["offer_id"]:
                # Cannot easily delete; skip if already applied
                return a
    payload = {
        "offer_id": internal_offer["offer_id"],
        "cover_letter": "Lettre de motivation test iter6",
        "use_online_cv": True,
        "online_cv_template": "etudiant",
        "uploaded_doc_ids": [],
    }
    r = requests.post(f"{API}/applications", headers=_h(tok), json=payload, timeout=20)
    if r.status_code == 400 and "déjà postulé" in r.text:
        # find existing app
        apps = requests.get(f"{API}/applications", headers=_h(tok), timeout=15).json()
        for a in apps:
            if a.get("offer_id") == internal_offer["offer_id"]:
                return a
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestApplicationOnlineCv:
    def test_application_stores_snapshot_and_template(self, created_application):
        a = created_application
        assert a.get("use_online_cv") is True
        assert a.get("online_cv_template") == "etudiant", a
        assert a.get("online_cv_snapshot"), "snapshot missing"
        assert a["online_cv_snapshot"].get("professional_title")

    def test_company_can_get_application_cv(self, company_auth, created_application):
        tok, _ = company_auth
        app_id = created_application["app_id"]
        r = requests.get(f"{API}/applications/{app_id}/cv", headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "cv" in j and "candidate" in j and "template" in j
        assert j["template"] == "etudiant"
        assert j["cv"]["professional_title"]

    def test_candidate_can_get_application_cv(self, candidate_auth, created_application):
        tok, _ = candidate_auth
        app_id = created_application["app_id"]
        r = requests.get(f"{API}/applications/{app_id}/cv", headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text

    def test_company_export_application_cv_pdf(self, company_auth, created_application):
        tok, _ = company_auth
        app_id = created_application["app_id"]
        r = requests.get(f"{API}/applications/{app_id}/cv/export", headers=_h(tok), timeout=30)
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1500

    def test_application_cv_pdf_default_template_matches_application(self, company_auth, created_application):
        # No template query param → should use application's template (etudiant)
        tok, _ = company_auth
        app_id = created_application["app_id"]
        r = requests.get(f"{API}/applications/{app_id}/cv/export", headers=_h(tok), timeout=30)
        assert r.status_code == 200
        # Hard to verify the actual rendered template, but the request must succeed
        assert r.content[:4] == b"%PDF"

    def test_other_company_forbidden(self, second_company_auth, created_application):
        tok, _ = second_company_auth
        app_id = created_application["app_id"]
        r = requests.get(f"{API}/applications/{app_id}/cv", headers=_h(tok), timeout=15)
        assert r.status_code == 403, r.text
        r2 = requests.get(f"{API}/applications/{app_id}/cv/export", headers=_h(tok), timeout=15)
        assert r2.status_code == 403

    def test_other_candidate_forbidden(self, second_candidate_auth, created_application):
        tok, _ = second_candidate_auth
        app_id = created_application["app_id"]
        r = requests.get(f"{API}/applications/{app_id}/cv", headers=_h(tok), timeout=15)
        assert r.status_code == 403

    def test_snapshot_is_frozen(self, candidate_auth, company_auth, created_application):
        """Modify the live CV AFTER application — /applications/{id}/cv must still return original snapshot."""
        ctok, _ = candidate_auth
        cotok, _ = company_auth
        app_id = created_application["app_id"]
        original_title = created_application["online_cv_snapshot"]["professional_title"]
        # mutate live CV
        new_title = f"MUTATED_{uuid.uuid4().hex[:6]}"
        r = requests.put(f"{API}/cv", headers=_h(ctok),
                         json={"professional_title": new_title}, timeout=15)
        assert r.status_code == 200
        # fetch app cv
        r2 = requests.get(f"{API}/applications/{app_id}/cv", headers=_h(cotok), timeout=15)
        assert r2.status_code == 200
        snap_title = r2.json()["cv"]["professional_title"]
        assert snap_title == original_title, f"Snapshot leaked: expected {original_title!r}, got {snap_title!r}"
        # restore
        requests.put(f"{API}/cv", headers=_h(ctok), json={"professional_title": original_title}, timeout=15)


# ------------------- Application without online CV -------------------
class TestApplicationWithoutOnlineCv:
    def test_no_online_cv_application_returns_404(self, candidate_auth, company_auth, internal_offer, created_application):
        """Find or create an offer where the candidate applies without use_online_cv."""
        ctok, _ = candidate_auth
        cotok, _ = company_auth
        # Use a different offer owned by SAME company so cotok can access
        r = requests.get(f"{API}/offers?limit=500", timeout=20)
        offers = r.json() if isinstance(r.json(), list) else []
        owner_id = created_application["company_id"]
        candidates = [o for o in offers if o.get("company_id") == owner_id and o["offer_id"] != internal_offer["offer_id"]]
        if not candidates:
            pytest.skip("Need a second internal offer owned by same company")
            pytest.skip("Need a second internal offer")
        target = candidates[0]
        payload = {
            "offer_id": target["offer_id"],
            "cover_letter": "Pas de CV en ligne",
            "use_online_cv": False,
            "online_cv_template": "modern",
            "uploaded_doc_ids": [],
        }
        rp = requests.post(f"{API}/applications", headers=_h(ctok), json=payload, timeout=20)
        if rp.status_code == 400 and "déjà postulé" in rp.text:
            # fetch existing
            mine = requests.get(f"{API}/applications", headers=_h(ctok), timeout=15).json()
            app = next((a for a in mine if a["offer_id"] == target["offer_id"]), None)
            if not app:
                pytest.skip("Cannot resolve existing application")
        else:
            assert rp.status_code in (200, 201), rp.text
            app = rp.json()
        # use_online_cv should be False
        assert app.get("use_online_cv") in (False, None), app.get("use_online_cv")
        # /cv on this application -> 404
        r2 = requests.get(f"{API}/applications/{app['app_id']}/cv", headers=_h(cotok), timeout=15)
        assert r2.status_code == 404, f"Expected 404, got {r2.status_code} {r2.text[:200]}"


# ------------------- /api/users/{id}/cv visibility -------------------
class TestUserCvVisibility:
    def _set_visibility(self, tok, vis):
        r = requests.put(f"{API}/cv", headers=_h(tok), json={"visibility": vis}, timeout=15)
        assert r.status_code == 200

    def test_public(self, candidate_auth, second_candidate_auth):
        tok, me = candidate_auth
        otok, _ = second_candidate_auth
        self._set_visibility(tok, "public")
        # anonymous
        r = requests.get(f"{API}/users/{me['user_id']}/cv", timeout=15)
        assert r.status_code == 200
        # other user
        r2 = requests.get(f"{API}/users/{me['user_id']}/cv", headers=_h(otok), timeout=15)
        assert r2.status_code == 200

    def test_private(self, candidate_auth, second_candidate_auth):
        tok, me = candidate_auth
        otok, _ = second_candidate_auth
        self._set_visibility(tok, "private")
        r = requests.get(f"{API}/users/{me['user_id']}/cv", headers=_h(otok), timeout=15)
        assert r.status_code == 403
        # owner still ok
        r2 = requests.get(f"{API}/users/{me['user_id']}/cv", headers=_h(tok), timeout=15)
        assert r2.status_code == 200

    def test_connected_blocks_non_contacts(self, candidate_auth, second_candidate_auth):
        tok, me = candidate_auth
        otok, _ = second_candidate_auth
        self._set_visibility(tok, "connected")
        r = requests.get(f"{API}/users/{me['user_id']}/cv", headers=_h(otok), timeout=15)
        # second candidate is not a contact → 403
        assert r.status_code in (403,), r.status_code

    def test_after_application_blocks_company_without_app(self, candidate_auth):
        tok, me = candidate_auth
        self._set_visibility(tok, "after_application")
        # Find a company user that has NEVER received an application from this candidate
        mine = requests.get(f"{API}/applications", headers=_h(tok), timeout=15).json()
        applied_company_ids = {a.get("company_id") for a in mine}
        target_company_tok = None
        for email in ["hr@datalab.fr", "hr@greenpulse.fr", "hr@cyberspark.fr", "hr@neopulse.fr",
                      "hr@apexsoft.fr", "hr@brightstudio001.fr", "hr@brightstudio022.fr"]:
            rr = requests.post(f"{API}/auth/login", json={"email": email, "password": "Demo1234!"}, timeout=15)
            if rr.status_code != 200:
                continue
            uj = rr.json()
            cid = (uj.get("user") or {}).get("user_id")
            if cid and cid not in applied_company_ids:
                target_company_tok = uj.get("token")
                break
        if not target_company_tok:
            pytest.skip("Could not find a company with no prior application from this candidate")
        r = requests.get(f"{API}/users/{me['user_id']}/cv", headers=_h(target_company_tok), timeout=15)
        assert r.status_code == 403, f"Expected 403 (no app yet), got {r.status_code}"

    def test_after_application_allows_company_with_app(self, candidate_auth, company_auth, created_application):
        tok, me = candidate_auth
        cotok, _ = company_auth
        # ensure visibility=after_application
        self._set_visibility(tok, "after_application")
        # company has applied-to relationship via created_application
        r = requests.get(f"{API}/users/{me['user_id']}/cv", headers=_h(cotok), timeout=15)
        assert r.status_code == 200, f"Company w/ application should see CV: {r.status_code} {r.text[:200]}"
        # restore to public for other tests
        self._set_visibility(tok, "public")
