"""Email-driven auth flows — verification + password reset.

Endpoints:
- POST /api/auth/send-verification   (authenticated) — request a verification email
- GET  /api/auth/verify-email          — consume the token, mark email_verified=True
- POST /api/auth/forgot-password       — request a reset link (no body leak even if email unknown)
- POST /api/auth/reset-password        — consume a reset token + set a new password
- GET  /api/admin/auth-tokens/recent   (admin) — debug: see latest tokens (useful when running
                                                 without Resend configured)

Both reset and verification tokens are stored in dedicated MongoDB collections with TTL indexes
(handled in `ensure_indexes`), so expired rows are purged automatically.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from services.email import send_email, email_provider_status


RESET_TOKEN_TTL_HOURS = 1
VERIFY_TOKEN_TTL_HOURS = 24


def _frontend_origin(request: Request) -> str:
    explicit = os.environ.get("FRONTEND_URL", "").strip()
    if explicit:
        return explicit
    host = request.headers.get("host") or request.url.netloc
    scheme = "https"  # ingress always TLS-terminates
    return f"{scheme}://{host}"


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str


def register_email_auth_routes(api_router, db, get_current_user, hash_password):
    @api_router.post("/auth/send-verification")
    async def send_verification(request: Request, user=Depends(get_current_user)):
        """Generate a verification token and email it. Idempotent — old tokens
        for this user are revoked first."""
        if user.get("email_verified"):
            return {"ok": True, "already_verified": True}
        await db.email_verification_tokens.delete_many({"user_id": user["user_id"]})
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=VERIFY_TOKEN_TTL_HOURS)
        await db.email_verification_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "email": user["email"],
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "used_at": None,
        })
        link = f"{_frontend_origin(request)}/verify-email?token={token}"
        delivery = await send_email(
            to=user["email"],
            subject="Vérifiez votre adresse email — StageEtudiant",
            html=(
                f"<p>Bonjour {user.get('name','')},</p>"
                f"<p>Cliquez sur le lien ci-dessous pour confirmer votre adresse email :</p>"
                f"<p><a href=\"{link}\">{link}</a></p>"
                f"<p>Ce lien expire dans {VERIFY_TOKEN_TTL_HOURS}h.</p>"
            ),
            text=f"Confirmez votre email : {link}",
        )
        return {"ok": True, "delivery": delivery}

    @api_router.get("/auth/verify-email")
    async def verify_email(token: str):
        doc = await db.email_verification_tokens.find_one({"token": token})
        if not doc:
            raise HTTPException(400, "Lien invalide")
        if doc.get("used_at"):
            raise HTTPException(400, "Lien déjà utilisé")
        exp = doc.get("expires_at")
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and exp < datetime.now(timezone.utc):
            raise HTTPException(400, "Lien expiré")
        await db.users.update_one(
            {"user_id": doc["user_id"]},
            {"$set": {"email_verified": True, "email_verified_at": datetime.now(timezone.utc).isoformat()}},
        )
        await db.email_verification_tokens.update_one(
            {"token": token},
            {"$set": {"used_at": datetime.now(timezone.utc)}},
        )
        return {"ok": True}

    @api_router.post("/auth/forgot-password")
    async def forgot_password(data: ForgotPasswordIn, request: Request):
        """Always returns 200 to prevent email-enumeration. Generates a token
        only when the email is known; sends or logs the link via `send_email`."""
        user = await db.users.find_one({"email": data.email})
        if user:
            await db.password_reset_tokens.delete_many({"user_id": user["user_id"]})
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_TTL_HOURS)
            await db.password_reset_tokens.insert_one({
                "token": token,
                "user_id": user["user_id"],
                "email": user["email"],
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
                "used_at": None,
            })
            link = f"{_frontend_origin(request)}/reset-password/{token}"
            await send_email(
                to=user["email"],
                subject="Réinitialisation de votre mot de passe — StageEtudiant",
                html=(
                    f"<p>Bonjour {user.get('name','')},</p>"
                    f"<p>Vous avez demandé à réinitialiser votre mot de passe. Cliquez sur ce lien :</p>"
                    f"<p><a href=\"{link}\">{link}</a></p>"
                    f"<p>Ce lien expire dans {RESET_TOKEN_TTL_HOURS}h. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>"
                ),
                text=f"Réinitialisez votre mot de passe : {link}",
            )
        # Same response whether the email exists or not.
        return {"ok": True, "message": "Si cette adresse est connue, un email a été envoyé."}

    @api_router.post("/auth/reset-password")
    async def reset_password(data: ResetPasswordIn):
        if len(data.password) < 8:
            raise HTTPException(400, "Le mot de passe doit faire au moins 8 caractères")
        doc = await db.password_reset_tokens.find_one({"token": data.token})
        if not doc:
            raise HTTPException(400, "Lien invalide")
        if doc.get("used_at"):
            raise HTTPException(400, "Lien déjà utilisé")
        exp = doc.get("expires_at")
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and exp < datetime.now(timezone.utc):
            raise HTTPException(400, "Lien expiré")
        await db.users.update_one(
            {"user_id": doc["user_id"]},
            {"$set": {"password": hash_password(data.password)}},
        )
        await db.password_reset_tokens.update_one(
            {"token": data.token},
            {"$set": {"used_at": datetime.now(timezone.utc)}},
        )
        return {"ok": True}

    @api_router.get("/admin/auth-tokens/recent")
    async def list_recent_tokens(user=Depends(get_current_user)):
        """Admin-only debug helper to reveal the last issued tokens — useful
        when running without Resend (dev mode). Returns email + link, never
        passwords."""
        if user["role"] != "admin":
            raise HTTPException(403, "Admin uniquement")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        resets = await db.password_reset_tokens.find(
            {"created_at": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("created_at", -1).limit(10).to_list(10)
        verifs = await db.email_verification_tokens.find(
            {"created_at": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("created_at", -1).limit(10).to_list(10)

        def _serialize(items, kind):
            out = []
            for t in items:
                out.append({
                    "kind": kind,
                    "email": t.get("email"),
                    "token": t.get("token"),
                    "created_at": t.get("created_at").isoformat() if isinstance(t.get("created_at"), datetime) else t.get("created_at"),
                    "expires_at": t.get("expires_at").isoformat() if isinstance(t.get("expires_at"), datetime) else t.get("expires_at"),
                    "used": bool(t.get("used_at")),
                })
            return out
        return {
            "provider": email_provider_status(),
            "password_reset": _serialize(resets, "password_reset"),
            "email_verification": _serialize(verifs, "email_verification"),
        }
