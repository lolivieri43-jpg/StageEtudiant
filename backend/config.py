"""Central environment configuration with backwards-compatible aliases.

Every backend module should read its secrets through this module rather
than calling `os.environ.get(...)` directly, so we have a single place to
- enforce the canonical variable names (e.g. `FRANCE_TRAVAIL_CLIENT_ID`)
- still accept legacy aliases (e.g. `FT_CLIENT_ID`) without breaking
  existing `.env` files on VPS deployments,
- and expose a non-secret health summary for the admin diagnostic endpoint.

NO VALUES ARE EXPOSED. Only "present" / "missing" booleans leave this module.
"""
from __future__ import annotations

import os
from typing import Optional


# ---------- Helpers -------------------------------------------------------
def _first(*names: str, default: Optional[str] = None) -> Optional[str]:
    """Return the first env var that is set and non-empty among `names`."""
    for n in names:
        v = os.environ.get(n)
        if v is not None and v.strip() != "":
            return v.strip()
    return default


def _present(value: Optional[str]) -> bool:
    """A value counts as present only if non-empty and not a placeholder."""
    if not value:
        return False
    v = value.strip()
    if not v:
        return False
    if v.startswith("xxxx") or v.startswith("YOUR_") or v.startswith("CHANGE_ME"):
        return False
    return True


# ---------- Resolvers (the only public API of this module) ----------------
def google_client_id() -> Optional[str]:
    return _first("GOOGLE_CLIENT_ID")


def google_client_secret() -> Optional[str]:
    return _first("GOOGLE_CLIENT_SECRET")


def google_redirect_uri() -> Optional[str]:
    """Explicit override for the OAuth callback URL. When unset, the OAuth
    handler auto-builds it from the live request `Host` header — that is
    fine for preview but production deployments behind a CDN may need to
    pin the value explicitly here."""
    return _first("GOOGLE_REDIRECT_URI")


def frontend_url() -> Optional[str]:
    return _first("FRONTEND_URL")


def backend_url() -> Optional[str]:
    return _first("BACKEND_URL")


def france_travail_client_id() -> Optional[str]:
    """Canonical name: `FRANCE_TRAVAIL_CLIENT_ID`. Legacy `FT_CLIENT_ID` is
    still accepted so existing VPS `.env` files keep working."""
    return _first("FRANCE_TRAVAIL_CLIENT_ID", "FT_CLIENT_ID")


def france_travail_client_secret() -> Optional[str]:
    return _first("FRANCE_TRAVAIL_CLIENT_SECRET", "FT_CLIENT_SECRET")


def adzuna_app_id() -> Optional[str]:
    return _first("ADZUNA_APP_ID")


def adzuna_app_key() -> Optional[str]:
    return _first("ADZUNA_APP_KEY")


def jooble_api_key() -> Optional[str]:
    return _first("JOOBLE_API_KEY")


def apify_token() -> Optional[str]:
    return _first("APIFY_TOKEN")


def apify_eures_actor() -> str:
    return _first("APIFY_EURES_ACTOR", default="lexis-solutions~eures-eu-jobs-scraper")


def openai_api_key() -> Optional[str]:
    """Canonical `OPENAI_API_KEY` with `EMERGENT_LLM_KEY` as fallback for
    backwards-compat with the Emergent platform's universal key."""
    return _first("OPENAI_API_KEY", "EMERGENT_LLM_KEY")


def ai_search_model() -> str:
    return _first("AI_SEARCH_MODEL", default="gpt-4.1-mini")


def session_secret() -> Optional[str]:
    return _first("SESSION_SECRET")


def jwt_secret() -> str:
    """JWT_SECRET has a hard-coded fallback so the app boots on first run,
    but production MUST override it via env. The diagnostic endpoint will
    report it as MISSING when the default is in use."""
    return _first("JWT_SECRET", default="stagiaire-connect-secret-2026-very-long-key")


def jwt_secret_is_default() -> bool:
    return _first("JWT_SECRET") is None


def resend_api_key() -> Optional[str]:
    return _first("RESEND_API_KEY")


def resend_from_email() -> str:
    return _first("RESEND_FROM_EMAIL", default="onboarding@resend.dev")


def geoapify_api_key() -> Optional[str]:
    return _first("GEOAPIFY_API_KEY")


def lba_api_token() -> Optional[str]:
    return _first("LBA_API_TOKEN")


# ---------- Diagnostic snapshot (no secrets leak) -------------------------
# Schema: ordered list of (group, label, present_bool, used_alias_or_None).
def env_diagnostic() -> dict:
    """Returns a JSON-friendly snapshot of which env vars are configured.
    NO VALUES ARE INCLUDED — only `"OK"` or `"MANQUANT"` plus, where
    applicable, the alias name that was actually picked up so admins can
    spot deviations from the canonical naming."""

    def _row(canonical: str, value: Optional[str], aliases: tuple = ()) -> dict:
        ok = _present(value)
        # Which name actually held the value? Useful when a legacy alias is in play.
        picked_from: Optional[str] = None
        if ok:
            for n in (canonical, *aliases):
                if _present(os.environ.get(n)):
                    picked_from = n
                    break
        return {
            "name": canonical,
            "status": "OK" if ok else "MANQUANT",
            "picked_from": picked_from,
            "aliases_accepted": list(aliases) or None,
        }

    return {
        "auth": [
            _row("GOOGLE_CLIENT_ID", google_client_id()),
            _row("GOOGLE_CLIENT_SECRET", google_client_secret()),
            _row("GOOGLE_REDIRECT_URI", google_redirect_uri()),
            _row("JWT_SECRET", None if jwt_secret_is_default() else "set"),
            _row("SESSION_SECRET", session_secret()),
        ],
        "platform": [
            _row("FRONTEND_URL", frontend_url()),
            _row("BACKEND_URL", backend_url()),
        ],
        "jobs_apis": [
            _row("FRANCE_TRAVAIL_CLIENT_ID", france_travail_client_id(),
                 aliases=("FT_CLIENT_ID",)),
            _row("FRANCE_TRAVAIL_CLIENT_SECRET", france_travail_client_secret(),
                 aliases=("FT_CLIENT_SECRET",)),
            _row("ADZUNA_APP_ID", adzuna_app_id()),
            _row("ADZUNA_APP_KEY", adzuna_app_key()),
            _row("JOOBLE_API_KEY", jooble_api_key()),
            _row("APIFY_TOKEN", apify_token()),
            _row("APIFY_EURES_ACTOR", _first("APIFY_EURES_ACTOR")),
            _row("LBA_API_TOKEN", lba_api_token()),
        ],
        "ai": [
            _row("OPENAI_API_KEY", openai_api_key(), aliases=("EMERGENT_LLM_KEY",)),
            _row("AI_SEARCH_MODEL", _first("AI_SEARCH_MODEL") or ai_search_model()),
        ],
        "email": [
            _row("RESEND_API_KEY", resend_api_key()),
            _row("RESEND_FROM_EMAIL", _first("RESEND_FROM_EMAIL") or resend_from_email()),
        ],
        "geocoding": [
            _row("GEOAPIFY_API_KEY", geoapify_api_key()),
        ],
    }
