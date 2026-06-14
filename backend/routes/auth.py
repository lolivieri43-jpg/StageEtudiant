"""Auth routes — split from server.py for maintainability.

Endpoints:
- POST /api/auth/register   — email/password sign-up (with reserved-name guard)
- POST /api/auth/login      — email/password login
- POST /api/auth/session    — Emergent Google OAuth session exchange
- GET  /api/auth/me         — current authenticated user
- POST /api/auth/logout     — clear session cookie
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from typing import Literal


UserRole = Literal["candidate", "company", "admin"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SessionIn(BaseModel):
    session_id: str


# Names that may not be used as account display names (reserved for the platform itself).
RESERVED_REGISTER_NAMES = {
    "stageetudiant", "stageetudiantcom", "stageetudiantofficiel",
    "stagiaireconnect", "support", "moderation", "admin",
}


def register_auth_routes(api_router, db, get_current_user, hash_password, verify_password,
                         create_jwt, clean_user, update_online, set_auth_cookie, clear_auth_cookie):
    @api_router.post("/auth/register")
    async def register(data: RegisterIn, response: Response):
        existing = await db.users.find_one({"email": data.email}, {"_id": 0})
        if existing:
            raise HTTPException(400, "Email déjà utilisé")
        from geo_search import normalize_text as _norm
        name_norm = _norm(data.name).replace(" ", "").replace(".", "")
        if name_norm in RESERVED_REGISTER_NAMES:
            raise HTTPException(400, "Ce nom est réservé à la plateforme. Veuillez en choisir un autre.")
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        profile: dict = {}
        if data.role == "candidate":
            parts = data.name.strip().split(" ", 1)
            profile = {"first_name": parts[0], "last_name": parts[1] if len(parts) > 1 else "", "status": "en_recherche"}
        elif data.role == "company":
            profile = {"company_name": data.name, "verified": False}
        doc = {
            "user_id": user_id,
            "email": data.email,
            "password": hash_password(data.password),
            "name": data.name,
            "role": data.role,
            "profile": profile,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(doc)
        token = create_jwt(user_id)
        set_auth_cookie(response, token)
        return {"token": token, "user": clean_user({**doc})}

    @api_router.post("/auth/login")
    async def login(data: LoginIn, response: Response):
        user = await db.users.find_one({"email": data.email})
        if not user or not user.get("password") or not verify_password(data.password, user["password"]):
            raise HTTPException(401, "Email ou mot de passe incorrect")
        await update_online(user["user_id"])
        token = create_jwt(user["user_id"])
        set_auth_cookie(response, token)
        return {"token": token, "user": clean_user({**user})}

    @api_router.post("/auth/session")
    async def emergent_session(data: SessionIn, response: Response):
        try:
            r = requests.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": data.session_id},
                timeout=10,
            )
            if r.status_code != 200:
                raise HTTPException(401, "Session invalide")
            info = r.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Auth provider error: {e}")
        email = info["email"]
        name = info.get("name", email.split("@")[0])
        picture = info.get("picture")
        session_token = info["session_token"]
        user = await db.users.find_one({"email": email})
        if not user:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            parts = name.strip().split(" ", 1)
            user = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "role": "candidate",
                "profile": {
                    "first_name": parts[0],
                    "last_name": parts[1] if len(parts) > 1 else "",
                    "avatar": picture,
                    "status": "en_recherche",
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
            await db.users.insert_one(user)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        response.set_cookie(
            "session_token", session_token,
            max_age=7 * 24 * 3600, httponly=True, secure=True, samesite="none", path="/",
        )
        return {"user": clean_user({**user}), "token": session_token}

    @api_router.get("/auth/me")
    async def me(user=Depends(get_current_user)):
        await update_online(user["user_id"])
        return user

    @api_router.post("/auth/logout")
    async def logout(request: Request, response: Response):
        token = request.cookies.get("session_token")
        if token:
            await db.user_sessions.delete_many({"session_token": token})
        response.delete_cookie("session_token", path="/")
        clear_auth_cookie(response)
        return {"ok": True}
