"""Shared test fixtures — credentials are loaded from env with documented test defaults.

These are NOT production secrets. They reference seeded test accounts described in
/app/memory/test_credentials.md. Override them per-CI by setting the matching env vars.
"""
import os

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "bernardolivieri1326@gmail.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "OwnerAdmin2026!")

LEGACY_ADMIN_EMAIL = os.environ.get("TEST_LEGACY_ADMIN_EMAIL", "admin@stagiaireconnect.fr")
LEGACY_ADMIN_PASSWORD = os.environ.get("TEST_LEGACY_ADMIN_PASSWORD", "Admin123!")

CANDIDATE_EMAIL = os.environ.get("TEST_CANDIDATE_EMAIL", "lucas.martin@email.fr")
CANDIDATE_PASSWORD = os.environ.get("TEST_CANDIDATE_PASSWORD", "Demo1234!")

COMPANY_EMAIL = os.environ.get("TEST_COMPANY_EMAIL", "hr@technova.fr")
COMPANY_PASSWORD = os.environ.get("TEST_COMPANY_PASSWORD", "Demo1234!")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://joblink-stages.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
