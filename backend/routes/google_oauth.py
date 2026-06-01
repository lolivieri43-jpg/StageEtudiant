"""Google OAuth 2.0 — production-grade.

Endpoints:
- GET /api/auth/google           → 302 redirect to Google authorize URL (with anti-CSRF state)
- GET /api/auth/google/callback  → exchange code, link/create user, return JWT to frontend

REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
The redirect_uri is computed from the live request host so the same code works on the preview
URL (joblink-stages.preview.emergentagent.com) AND on the production domain (stageetudiant.com)
once the DNS points to the deploy. Both must be whitelisted in Google Cloud Console.
"""
from __future__ import annotations

import logging
import os
import secrets
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse


logger = logging.getLogger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"


def _build_redirect_uri(request: Request) -> str:
    """Compute the callback URL from the current request — never hardcoded.
    Forces HTTPS to match the production setup (Cloudflare/K8s ingress always TLS-terminates)."""
    host = request.headers.get("host") or request.url.netloc
    return f"https://{host}/api/auth/google/callback"


def register_google_oauth_routes(api_router, db, create_jwt):
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    frontend_url = os.environ.get("FRONTEND_URL", "")

    def _is_configured() -> bool:
        return bool(client_id) and bool(client_secret) and not client_id.startswith("xxxx")

    @api_router.get("/auth/google")
    async def google_login(request: Request):
        """Step 1 — redirect the user to Google's consent screen."""
        if not _is_configured():
            raise HTTPException(503, "Google OAuth non configuré (GOOGLE_CLIENT_ID/SECRET manquants)")
        state = secrets.token_urlsafe(24)
        # Persist state for one-time use (CSRF protection); auto-expire after 10 min.
        await db.oauth_states.insert_one({
            "state": state,
            "provider": "google",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        redirect_uri = _build_redirect_uri(request)
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": GOOGLE_SCOPES,
            "access_type": "online",
            "prompt": "select_account",
            "state": state,
        }
        url = f"{GOOGLE_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url, status_code=302)

    async def _resolve_frontend_url(request: Request) -> str:
        # Prefer the explicit FRONTEND_URL when host matches, otherwise use the request host.
        host = request.headers.get("host") or request.url.netloc
        return frontend_url or f"https://{host}"

    @api_router.get("/auth/google/callback")
    async def google_callback(request: Request):
        """Step 2 — exchange `code` for tokens, fetch userinfo, link or create user, redirect."""
        if not _is_configured():
            raise HTTPException(503, "Google OAuth non configuré")
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        err = request.query_params.get("error")
        front = await _resolve_frontend_url(request)
        if err:
            return RedirectResponse(f"{front}/login?google_error={urllib.parse.quote(err)}", status_code=302)
        if not code or not state:
            raise HTTPException(400, "Paramètres OAuth manquants (code/state)")
        consumed = await db.oauth_states.find_one_and_delete({"state": state, "provider": "google"})
        if not consumed:
            raise HTTPException(400, "state OAuth invalide ou expiré (anti-CSRF)")
        redirect_uri = _build_redirect_uri(request)
        async with httpx.AsyncClient(timeout=15.0) as client:
            tok_resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            if tok_resp.status_code != 200:
                logger.error(f"Google token exchange failed: {tok_resp.status_code} {tok_resp.text}")
                raise HTTPException(400, "Échec de l'échange de jeton Google")
            access_token = tok_resp.json().get("access_token")
            if not access_token:
                raise HTTPException(400, "Token Google manquant")
            ui_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ui_resp.status_code != 200:
                raise HTTPException(400, "Impossible de récupérer le profil Google")
            info = ui_resp.json()
        email = (info.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(400, "Email Google manquant")
        if not info.get("email_verified"):
            return RedirectResponse(f"{front}/login?google_error=email_not_verified", status_code=302)
        google_id = info.get("sub")
        given = info.get("given_name") or ""
        family = info.get("family_name") or ""
        full_name = (info.get("name") or f"{given} {family}").strip() or email.split("@")[0]
        picture = info.get("picture")
        now = datetime.now(timezone.utc).isoformat()
        existing = await db.users.find_one({"email": email})
        if existing:
            updates = {
                "google_id": google_id,
                "provider": existing.get("provider") or "google",
                "email_verified": True,
                "last_seen": now,
            }
            profile = existing.get("profile", {}) or {}
            if picture and not profile.get("avatar") and not profile.get("logo"):
                key = "logo" if existing.get("role") == "company" else "avatar"
                profile[key] = picture
                updates["profile"] = profile
            await db.users.update_one({"user_id": existing["user_id"]}, {"$set": updates})
            user = existing
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            user = {
                "user_id": user_id,
                "email": email,
                "name": full_name,
                "role": None,  # role chosen via /choose-role after first login
                "google_id": google_id,
                "provider": "google",
                "email_verified": True,
                "profile": {
                    "first_name": given,
                    "last_name": family,
                    "avatar": picture,
                },
                "created_at": now,
                "updated_at": now,
                "last_seen": now,
            }
            await db.users.insert_one(user)
        token = create_jwt(user["user_id"])
        next_path = "/choose-role" if not user.get("role") else (
            "/admin" if user["role"] == "admin"
            else ("/dashboard" if user["role"] in ("candidate", "company") else "/")
        )
        # Pass JWT via fragment so it isn't logged by intermediary proxies.
        redirect = f"{front}{next_path}#token={token}"
        return RedirectResponse(redirect, status_code=302)
