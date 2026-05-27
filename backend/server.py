"""FastAPI backend for StageEtudiant - French stage/alternance platform."""
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import math
import json as _json
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Dict, Set
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import requests
from collections import Counter, defaultdict

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ.get('JWT_SECRET', 'stagiaire-connect-secret-2026-very-long-key')
JWT_ALG = 'HS256'

app = FastAPI(title="StageEtudiant API")
api = APIRouter(prefix="/api")

# ============ MODELS ============
UserRole = Literal["candidate", "company", "admin"]

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    name: str  # company name OR full name "Prénom Nom"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class SessionIn(BaseModel):
    session_id: str

class CandidateProfileIn(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    avatar: Optional[str] = None
    banner: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    school: Optional[str] = None
    level: Optional[str] = None  # Bac+2, Bac+3, Bac+5...
    domain: Optional[str] = None
    contract_type: Optional[str] = None  # stage, alternance, les_deux
    duration: Optional[str] = None
    availability: Optional[str] = None
    skills: Optional[List[str]] = None
    experiences: Optional[List[dict]] = None
    description: Optional[str] = None
    cv_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    status: Optional[str] = "en_recherche"  # en_recherche, a_l_ecoute, non_disponible
    mobile: Optional[str] = None

class CompanyProfileIn(BaseModel):
    company_name: Optional[str] = None
    logo: Optional[str] = None
    banner: Optional[str] = None
    sector: Optional[str] = None
    size: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    siret: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    hr_contact: Optional[str] = None
    pro_email: Optional[str] = None
    phone: Optional[str] = None
    recruiting_domains: Optional[List[str]] = None

class OfferIn(BaseModel):
    title: str
    contract_type: Literal["stage", "alternance"]
    domain: str
    city: str
    region: str
    remote: bool = False
    duration: str
    rhythm: Optional[str] = None
    start_date: Optional[str] = None
    level: str
    skills: List[str] = []
    description: str
    profile: Optional[str] = None
    benefits: Optional[str] = None
    salary: Optional[str] = None

class ApplicationIn(BaseModel):
    offer_id: str
    cover_letter: Optional[str] = None
    use_online_cv: bool = True
    online_cv_template: Optional[str] = "modern"
    uploaded_doc_ids: List[str] = []

# ---- Shared Pydantic models imported from /app/backend/models.py to avoid duplication ----
from models import (
    PostIn, PostMedia, LinkPreview, CommentIn,
    MessageIn, MessageAttachment, ContactRequestIn, DealIn,
)

# ============ HELPERS ============
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_jwt(user_id: str) -> str:
    payload = {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

async def get_current_user(request: Request):
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    # Try session_token first (Emergent)
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if session:
        expires_at = session.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise HTTPException(401, "Session expired")
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password": 0})
        if user:
            return user
    # Try JWT
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user = await db.users.find_one({"user_id": payload["user_id"]}, {"_id": 0, "password": 0})
        if user:
            return user
    except Exception:
        pass
    raise HTTPException(401, "Invalid token")

async def get_optional_user(request: Request):
    try:
        return await get_current_user(request)
    except Exception:
        return None

async def update_online(user_id: str):
    await db.users.update_one({"user_id": user_id}, {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}})

async def notify(user_id: str, kind: str, message: str, link: Optional[str] = None, from_user: Optional[dict] = None):
    await db.notifications.insert_one({
        "notif_id": f"n_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "kind": kind,
        "message": message,
        "link": link,
        "from_user": from_user,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

def clean_user(u: dict) -> dict:
    if not u:
        return u
    u.pop("password", None)
    u.pop("_id", None)
    return u

# ============ AUTH ============
@api.post("/auth/register")
async def register(data: RegisterIn):
    existing = await db.users.find_one({"email": data.email}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Email déjà utilisé")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    profile = {}
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
    return {"token": token, "user": clean_user({**doc})}

@api.post("/auth/login")
async def login(data: LoginIn):
    user = await db.users.find_one({"email": data.email})
    if not user or not user.get("password") or not verify_password(data.password, user["password"]):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    await update_online(user["user_id"])
    token = create_jwt(user["user_id"])
    return {"token": token, "user": clean_user({**user})}

@api.post("/auth/session")
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
            "profile": {"first_name": parts[0], "last_name": parts[1] if len(parts) > 1 else "", "avatar": picture, "status": "en_recherche"},
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
    response.set_cookie("session_token", session_token, max_age=7*24*3600, httponly=True, secure=True, samesite="none", path="/")
    return {"user": clean_user({**user}), "token": session_token}

@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    await update_online(user["user_id"])
    return user

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

# ============ PROFILES ============
@api.put("/profile")
async def update_profile(data: dict, user=Depends(get_current_user)):
    profile = user.get("profile", {})
    profile.update({k: v for k, v in data.items() if v is not None})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"profile": profile}})
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password": 0})
    return updated

@api.get("/users/{user_id}")
async def get_user_public(user_id: str, viewer=Depends(get_optional_user)):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password": 0})
    if not u:
        raise HTTPException(404, "Utilisateur introuvable")
    # Log a profile view (Phase A — a2). Dedupe: 1 view per (viewer,viewed) per 30 minutes.
    if viewer and viewer["user_id"] != user_id:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            recent = await db.profile_views.find_one({
                "viewer_user_id": viewer["user_id"],
                "viewed_user_id": user_id,
                "viewed_at": {"$gte": cutoff},
            })
            if not recent:
                await db.profile_views.insert_one({
                    "view_id": f"pv_{uuid.uuid4().hex[:12]}",
                    "viewer_user_id": viewer["user_id"],
                    "viewer_name": viewer.get("name"),
                    "viewer_avatar": viewer.get("profile", {}).get("avatar") or viewer.get("profile", {}).get("logo"),
                    "viewer_role": viewer.get("role"),
                    "viewed_user_id": user_id,
                    "viewed_role": u.get("role"),
                    "viewed_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.warning(f"profile_view log failed: {e}")
    return u

@api.get("/users")
async def list_users(role: Optional[str] = None, limit: int = 20):
    q = {}
    if role:
        q["role"] = role
    users = await db.users.find(q, {"_id": 0, "password": 0}).limit(limit).to_list(limit)
    return users

# ============ OFFERS ============
@api.post("/offers")
async def create_offer(data: OfferIn, user=Depends(get_current_user)):
    if user["role"] != "company":
        raise HTTPException(403, "Réservé aux entreprises")
    offer_id = f"off_{uuid.uuid4().hex[:12]}"
    doc = {
        "offer_id": offer_id,
        "company_id": user["user_id"],
        "company_name": user.get("profile", {}).get("company_name") or user["name"],
        "company_logo": user.get("profile", {}).get("logo"),
        "verified": user.get("profile", {}).get("verified", False),
        **data.model_dump(),
        "views": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.offers.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/offers")
async def list_offers(
    q: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    contract_type: Optional[str] = None,
    domain: Optional[str] = None,
    level: Optional[str] = None,
    remote: Optional[bool] = None,
    company_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 200,
):
    query = {}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"domain": {"$regex": q, "$options": "i"}},
        ]
    if region: query["region"] = region
    if city: query["city"] = {"$regex": city, "$options": "i"}
    if contract_type: query["contract_type"] = contract_type
    if domain: query["domain"] = {"$regex": domain, "$options": "i"}
    if level: query["level"] = level
    if remote is not None: query["remote"] = remote
    if company_id: query["company_id"] = company_id
    if source: query["source"] = source
    # Phase F: never show demo offers in production listings
    query["is_demo"] = {"$ne": True}
    # Sort: source_priority DESC (StageEtudiant first), then date DESC
    offers = await db.offers.find(query, {"_id": 0}).sort([("source_priority", -1), ("created_at", -1)]).limit(min(limit, 500)).to_list(min(limit, 500))
    return offers

@api.get("/offers/regions")
async def offers_by_region():
    offers = await db.offers.find({}, {"_id": 0, "region": 1, "company_id": 1}).to_list(1000)
    region_offers = Counter(o["region"] for o in offers if o.get("region"))
    region_companies = {}
    for o in offers:
        r = o.get("region")
        if r:
            region_companies.setdefault(r, set()).add(o["company_id"])
    return {
        "by_region": [
            {"region": r, "offers": region_offers[r], "companies": len(region_companies.get(r, set()))}
            for r in region_offers
        ]
    }

@api.get("/offers/{offer_id}")
async def get_offer(offer_id: str):
    offer = await db.offers.find_one({"offer_id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(404, "Offre introuvable")
    await db.offers.update_one({"offer_id": offer_id}, {"$inc": {"views": 1}})
    offer["views"] = offer.get("views", 0) + 1
    return offer

@api.delete("/offers/{offer_id}")
async def delete_offer(offer_id: str, user=Depends(get_current_user)):
    offer = await db.offers.find_one({"offer_id": offer_id})
    if not offer:
        raise HTTPException(404, "Introuvable")
    if offer["company_id"] != user["user_id"] and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    await db.offers.delete_one({"offer_id": offer_id})
    return {"ok": True}

# ============ APPLICATIONS ============
@api.post("/applications")
async def apply(data: ApplicationIn, user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Réservé aux candidats")
    offer = await db.offers.find_one({"offer_id": data.offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(404, "Offre introuvable")
    existing = await db.applications.find_one({"offer_id": data.offer_id, "candidate_id": user["user_id"]})
    if existing:
        raise HTTPException(400, "Vous avez déjà postulé")
    app_id = f"app_{uuid.uuid4().hex[:12]}"
    # Snapshot of online CV (if requested) so company always sees the CV as it was at apply time
    online_cv_snapshot = None
    if data.use_online_cv:
        cv_doc = await db.student_cvs.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if cv_doc:
            online_cv_snapshot = cv_doc
    # Resolve user's selected uploaded documents
    selected_docs = []
    if data.uploaded_doc_ids:
        docs = await db.student_documents.find(
            {"user_id": user["user_id"], "doc_id": {"$in": data.uploaded_doc_ids}}, {"_id": 0}
        ).to_list(20)
        for d in docs:
            selected_docs.append({
                "doc_id": d.get("doc_id"),
                "file_id": d.get("file_id"),
                "filename": d.get("filename"),
                "doc_type": d.get("doc_type", "autre"),
            })
    doc = {
        "app_id": app_id,
        "offer_id": data.offer_id,
        "offer_title": offer["title"],
        "company_id": offer["company_id"],
        "company_name": offer.get("company_name"),
        "candidate_id": user["user_id"],
        "candidate_name": user["name"],
        "candidate_avatar": user.get("profile", {}).get("avatar"),
        "cover_letter": data.cover_letter,
        "cv_url": user.get("profile", {}).get("cv_url"),
        "use_online_cv": bool(data.use_online_cv and online_cv_snapshot),
        "online_cv_snapshot": online_cv_snapshot,
        "online_cv_template": data.online_cv_template or "modern",
        "selected_documents": selected_docs,
        "status": "envoyee",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.applications.insert_one(doc)
    await notify(offer["company_id"], "application", f"{user['name']} a postulé à \"{offer['title']}\"", f"/applications", {"user_id": user["user_id"], "name": user["name"]})
    doc.pop("_id", None)
    return doc

@api.get("/applications")
async def my_applications(user=Depends(get_current_user)):
    if user["role"] == "candidate":
        apps = await db.applications.find({"candidate_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    elif user["role"] == "company":
        apps = await db.applications.find({"company_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    else:
        apps = await db.applications.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return apps

@api.patch("/applications/{app_id}")
async def update_application(app_id: str, data: dict, user=Depends(get_current_user)):
    app_doc = await db.applications.find_one({"app_id": app_id}, {"_id": 0})
    if not app_doc:
        raise HTTPException(404, "Introuvable")
    if app_doc["company_id"] != user["user_id"] and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    status = data.get("status")
    if status in ("vue", "en_attente", "acceptee", "refusee"):
        await db.applications.update_one({"app_id": app_id}, {"$set": {"status": status}})
        await notify(app_doc["candidate_id"], "application_status", f"Votre candidature \"{app_doc['offer_title']}\" est maintenant: {status}", "/dashboard")
    return {"ok": True}

# ============ POSTS / FEED — moved to routes/posts.py ============
# ============ MESSAGES — moved to routes/messages.py ============

# ============ CONTACTS — moved to routes/contacts.py ============
# ============ NOTIFICATIONS — moved to routes/notifications.py ============

# ============ STATS / DASHBOARD ============
@api.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    if user["role"] == "company":
        offers_count = await db.offers.count_documents({"company_id": user["user_id"]})
        apps = await db.applications.find({"company_id": user["user_id"]}, {"_id": 0}).to_list(500)
        unread = await db.messages.count_documents({"to_id": user["user_id"], "read": False})
        pending_apps = sum(1 for a in apps if a.get("status") == "envoyee")
        offers = await db.offers.find({"company_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
        total_views = sum(o.get("views", 0) for o in offers)
        return {
            "offers_count": offers_count,
            "applications_count": len(apps),
            "pending_applications": pending_apps,
            "unread_messages": unread,
            "total_views": total_views,
            "offers": offers[:10],
            "recent_applications": apps[:10],
        }
    else:
        apps = await db.applications.find({"candidate_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
        unread = await db.messages.count_documents({"to_id": user["user_id"], "read": False})
        recommended = await db.offers.find({}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8)
        return {
            "applications_count": len(apps),
            "pending": sum(1 for a in apps if a.get("status") in ("envoyee", "vue", "en_attente")),
            "accepted": sum(1 for a in apps if a.get("status") == "acceptee"),
            "unread_messages": unread,
            "applications": apps[:10],
            "recommended_offers": recommended,
        }

# ============ ADMIN ============
@api.get("/admin/stats")
async def admin_stats(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin uniquement")
    return {
        "users": await db.users.count_documents({}),
        "companies": await db.users.count_documents({"role": "company"}),
        "candidates": await db.users.count_documents({"role": "candidate"}),
        "offers": await db.offers.count_documents({}),
        "applications": await db.applications.count_documents({}),
        "posts": await db.posts.count_documents({}),
    }

@api.get("/admin/users")
async def admin_users(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin uniquement")
    return await db.users.find({}, {"_id": 0, "password": 0}).to_list(500)

@api.post("/admin/verify/{user_id}")
async def verify_company(user_id: str, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin uniquement")
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(404, "Introuvable")
    p = target.get("profile", {})
    p["verified"] = True
    await db.users.update_one({"user_id": user_id}, {"$set": {"profile": p}})
    await db.offers.update_many({"company_id": user_id}, {"$set": {"verified": True}})
    return {"ok": True}

# ============ SEED ============
@api.post("/seed")
async def seed(force: bool = False):
    if not force:
        if await db.users.count_documents({}) > 5:
            return {"ok": True, "msg": "Déjà peuplé"}
    # clean
    for c in ["users", "offers", "applications", "posts", "comments", "messages", "conversations", "contacts", "contact_requests", "notifications", "user_sessions"]:
        await db[c].delete_many({})

    regions_data = [
        ("Île-de-France", "Paris"), ("Auvergne-Rhône-Alpes", "Lyon"), ("Nouvelle-Aquitaine", "Bordeaux"),
        ("Occitanie", "Toulouse"), ("Hauts-de-France", "Lille"), ("Provence-Alpes-Côte d'Azur", "Marseille"),
        ("Grand Est", "Strasbourg"), ("Pays de la Loire", "Nantes"), ("Bretagne", "Rennes"),
        ("Normandie", "Rouen"), ("Bourgogne-Franche-Comté", "Dijon"), ("Centre-Val de Loire", "Tours"),
        ("Corse", "Ajaccio"),
    ]
    sectors = ["Informatique", "Marketing", "Finance", "Design", "Ingénierie", "Commerce", "Communication", "RH"]
    company_names = ["TechNova", "DataLab", "GreenPulse", "MarketWave", "FinanceX", "BuildUp", "MediaSphere", "CodeFactory", "AlphaConseil", "PixelStudio"]
    avatars = [
        "https://images.unsplash.com/photo-1778014104491-981d197134e5?w=200",
        "https://images.unsplash.com/photo-1762753674498-73ec49feafc4?w=200",
        "https://images.unsplash.com/photo-1771898343647-bd979ad8cca5?w=200",
        "https://images.unsplash.com/photo-1762522921456-cdfe882d36c3?w=200",
    ]
    logos = [
        "https://images.unsplash.com/photo-1770012977129-19f856a1f935?w=200",
        "https://images.unsplash.com/photo-1761044591996-7a05341a3e12?w=200",
        "https://images.unsplash.com/photo-1770210217380-d78a69acdc77?w=200",
    ]

    # Admin
    admin_id = "user_admin0000"
    await db.users.insert_one({
        "user_id": admin_id, "email": "admin@stagiaireconnect.fr",
        "password": hash_password("Admin123!"), "name": "Admin", "role": "admin",
        "profile": {"verified": True},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Companies
    companies = []
    for i, name in enumerate(company_names):
        region, city = regions_data[i % len(regions_data)]
        cid = f"user_co{i:04d}xxxx"
        doc = {
            "user_id": cid,
            "email": f"hr@{name.lower()}.fr",
            "password": hash_password("Demo1234!"),
            "name": name, "role": "company",
            "profile": {
                "company_name": name,
                "logo": logos[i % len(logos)],
                "banner": "https://images.unsplash.com/photo-1758691736975-9f7f643d178e?w=1200",
                "sector": sectors[i % len(sectors)],
                "size": ["1-10", "11-50", "51-200", "200+"][i % 4],
                "city": city, "region": region,
                "siret": f"{1000000+i*123}00012",
                "website": f"https://{name.lower()}.fr",
                "description": f"{name} est une entreprise innovante basée à {city}. Nous recrutons des stagiaires et alternants motivés pour rejoindre nos équipes dynamiques.",
                "recruiting_domains": [sectors[i % len(sectors)]],
                "verified": i % 2 == 0,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(doc)
        companies.append(doc)

    # Candidates
    first_names = ["Lucas", "Emma", "Hugo", "Léa", "Nathan", "Camille", "Théo", "Manon", "Adam", "Sarah", "Maxime", "Chloé"]
    last_names = ["Martin", "Dubois", "Bernard", "Thomas", "Robert", "Petit", "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre"]
    titles = ["Étudiant en Informatique", "Étudiante en Marketing", "Designer UX/UI", "Étudiant en Commerce", "Data Analyst Junior", "Développeur Web", "Étudiante en RH"]
    candidates = []
    for i in range(12):
        region, city = regions_data[i % len(regions_data)]
        cid = f"user_ca{i:04d}xxxx"
        doc = {
            "user_id": cid,
            "email": f"{first_names[i].lower()}.{last_names[i].lower()}@email.fr",
            "password": hash_password("Demo1234!"),
            "name": f"{first_names[i]} {last_names[i]}",
            "role": "candidate",
            "profile": {
                "first_name": first_names[i], "last_name": last_names[i],
                "title": titles[i % len(titles)],
                "avatar": avatars[i % len(avatars)],
                "banner": "https://images.unsplash.com/photo-1758691736975-9f7f643d178e?w=1200",
                "city": city, "region": region,
                "school": ["IUT", "École de Commerce", "Université", "École d'Ingénieur"][i % 4],
                "level": ["Bac+2", "Bac+3", "Bac+5"][i % 3],
                "domain": sectors[i % len(sectors)],
                "contract_type": ["stage", "alternance"][i % 2],
                "duration": ["6 mois", "1 an", "2 ans"][i % 3],
                "skills": ["Python", "React", "Communication", "Excel", "Figma", "SQL"][:3 + i % 3],
                "description": f"Étudiant(e) motivé(e) recherchant un {['stage', 'alternance'][i % 2]} en {sectors[i % len(sectors)]} à partir de septembre.",
                "status": ["en_recherche", "a_l_ecoute"][i % 2],
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(doc)
        candidates.append(doc)

    # Offers
    offer_titles = [
        ("Développeur Full-Stack", "Informatique", "stage"),
        ("Alternant Marketing Digital", "Marketing", "alternance"),
        ("Data Analyst", "Informatique", "stage"),
        ("Assistant Communication", "Communication", "alternance"),
        ("Designer UX/UI", "Design", "stage"),
        ("Chargé de recrutement", "RH", "alternance"),
        ("Ingénieur DevOps", "Informatique", "alternance"),
        ("Commercial B2B", "Commerce", "stage"),
        ("Analyste Financier", "Finance", "alternance"),
        ("Développeur Mobile", "Informatique", "stage"),
        ("Chef de projet junior", "Marketing", "alternance"),
        ("Product Designer", "Design", "alternance"),
    ]
    for i, (title, dom, ct) in enumerate(offer_titles):
        c = companies[i % len(companies)]
        region = c["profile"]["region"]
        city = c["profile"]["city"]
        await db.offers.insert_one({
            "offer_id": f"off_{i:04d}xxxxxxxx",
            "company_id": c["user_id"],
            "company_name": c["profile"]["company_name"],
            "company_logo": c["profile"]["logo"],
            "verified": c["profile"]["verified"],
            "title": title, "contract_type": ct, "domain": dom,
            "city": city, "region": region,
            "remote": i % 3 == 0,
            "duration": "6 mois" if ct == "stage" else "1-2 ans",
            "rhythm": "3j entreprise / 2j école" if ct == "alternance" else None,
            "start_date": "Septembre 2026",
            "level": ["Bac+2", "Bac+3", "Bac+5"][i % 3],
            "skills": ["Communication", "Esprit d'équipe", dom],
            "description": f"Rejoignez {c['profile']['company_name']} en tant que {title}. Vous participerez à des projets ambitieux dans un environnement stimulant. Missions variées, encadrement de qualité, possibilité d'embauche à la clé.",
            "profile": f"Étudiant(e) en {dom}, motivé(e), curieux(se), avec un bon esprit d'équipe.",
            "benefits": "Tickets restaurant, télétravail partiel, mutuelle, gratification au-dessus du minimum légal.",
            "salary": "1200€ / mois" if ct == "alternance" else "Gratification 600€",
            "views": (i * 37) % 200,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
        })

    # Posts
    sample_posts = [
        (companies[0], "🚀 Nous recherchons 2 alternants en BTS SIO pour septembre à Lyon ! Postulez dès maintenant.", "annonce"),
        (candidates[0], "Je recherche une alternance en développement web autour de Bourg-en-Bresse. Disponible dès septembre !", "recherche"),
        (companies[2], "Félicitations à notre nouvelle équipe d'alternants qui vient de nous rejoindre 🎉", "general"),
        (candidates[3], "Premier jour de stage chez DataLab, l'équipe est top ! Hâte de découvrir le projet.", "general"),
        (companies[4], "Conseil aux candidats : soignez votre lettre de motivation, c'est ce qui fait souvent la différence.", "conseil"),
        (candidates[5], "Quels sont vos conseils pour réussir un entretien en alternance ? Je passe le mien la semaine prochaine !", "general"),
    ]
    for i, (author, content, cat) in enumerate(sample_posts):
        await db.posts.insert_one({
            "post_id": f"post_{i:04d}xxxxxxxx",
            "author_id": author["user_id"],
            "author_name": author["name"],
            "author_role": author["role"],
            "author_avatar": author["profile"].get("avatar") or author["profile"].get("logo"),
            "content": content,
            "category": cat,
            "likes": [candidates[j]["user_id"] for j in range(i % 5)],
            "comments_count": 0,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=i*3)).isoformat(),
        })

    return {"ok": True, "users": 23, "offers": 12, "posts": 6}

@api.get("/")
async def root():
    return {"name": "StageEtudiant API", "status": "ok"}

# ============ DEALS / BONS PLANS + MONETIZATION ============
try:
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "sk_test_emergent")

# Fixed price packages (defined server-side ONLY for security)
PACKAGES = {
    "sub_monthly": {"amount": 1.00, "currency": "eur", "kind": "subscription", "period": "monthly", "days": 30},
    "sub_yearly": {"amount": 10.00, "currency": "eur", "kind": "subscription", "period": "yearly", "days": 365},
    "boost_student": {"amount": 1.00, "currency": "eur", "kind": "boost", "actor": "candidate", "days": 7},
    "boost_company": {"amount": 10.00, "currency": "eur", "kind": "boost", "actor": "company", "days": 7},
}

DealStatus = Literal["draft", "pending", "published", "refused", "suspended", "expired"]

class CheckoutIn(BaseModel):
    package_id: str
    origin_url: str
    deal_id: Optional[str] = None  # required for boosts

async def company_subscription_active(company_id: str) -> bool:
    sub = await db.subscriptions.find_one({"company_id": company_id, "status": "active"}, {"_id": 0})
    if not sub:
        return False
    end = sub.get("end_date")
    if isinstance(end, str):
        end = datetime.fromisoformat(end)
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end and end < datetime.now(timezone.utc):
        await db.subscriptions.update_one({"sub_id": sub["sub_id"]}, {"$set": {"status": "expired"}})
        return False
    return True

# ============ DEALS — moved to routes/deals.py ============

# Subscription status
@api.get("/subscriptions/me")
async def my_subscription(user=Depends(get_current_user)):
    sub = await db.subscriptions.find_one({"company_id": user["user_id"], "status": "active"}, {"_id": 0})
    if sub and sub.get("end_date"):
        end = sub["end_date"]
        if isinstance(end, str):
            end_dt = datetime.fromisoformat(end)
            if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt < datetime.now(timezone.utc):
                await db.subscriptions.update_one({"sub_id": sub["sub_id"]}, {"$set": {"status": "expired"}})
                sub["status"] = "expired"
    history = await db.payment_transactions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"subscription": sub, "history": history}

@api.post("/subscriptions/cancel")
async def cancel_sub(user=Depends(get_current_user)):
    sub = await db.subscriptions.find_one({"company_id": user["user_id"], "status": "active"})
    if not sub:
        raise HTTPException(404, "Aucun abonnement actif")
    await db.subscriptions.update_one({"sub_id": sub["sub_id"]}, {"$set": {"status": "canceled"}})
    return {"ok": True}

# ============ PAYMENTS (Stripe Checkout) ============
@api.post("/payments/checkout")
async def create_checkout(body: CheckoutIn, request: Request, user=Depends(get_current_user)):
    if not STRIPE_AVAILABLE:
        raise HTTPException(500, "Module de paiement indisponible")
    pkg = PACKAGES.get(body.package_id)
    if not pkg:
        raise HTTPException(400, "Package invalide")
    if pkg["kind"] == "subscription" and user["role"] != "company":
        raise HTTPException(403, "Réservé aux entreprises")
    if pkg["kind"] == "boost":
        if not body.deal_id:
            raise HTTPException(400, "deal_id requis")
        deal = await db.deals.find_one({"deal_id": body.deal_id}, {"_id": 0})
        if not deal:
            raise HTTPException(404, "Bon plan introuvable")
        if deal["author_id"] != user["user_id"]:
            raise HTTPException(403, "Pas votre bon plan")
        if pkg["actor"] == "candidate" and user["role"] != "candidate":
            raise HTTPException(403, "Boost étudiant réservé aux étudiants")
        if pkg["actor"] == "company" and user["role"] != "company":
            raise HTTPException(403, "Boost entreprise réservé aux entreprises")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_co = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/payment/cancel"
    metadata = {
        "package_id": body.package_id,
        "user_id": user["user_id"],
        "user_role": user["role"],
        "kind": pkg["kind"],
    }
    if body.deal_id:
        metadata["deal_id"] = body.deal_id
    req = CheckoutSessionRequest(amount=pkg["amount"], currency=pkg["currency"], success_url=success_url, cancel_url=cancel_url, metadata=metadata)
    session = await stripe_co.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
        "session_id": session.session_id,
        "user_id": user["user_id"],
        "user_role": user["role"],
        "package_id": body.package_id,
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "kind": pkg["kind"],
        "deal_id": body.deal_id,
        "metadata": metadata,
        "payment_status": "pending",
        "status": "initiated",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.session_id}

async def fulfill_transaction(tx: dict):
    """Apply business effect once payment is confirmed (idempotent)."""
    if tx.get("fulfilled"):
        return
    pkg_id = tx["package_id"]
    pkg = PACKAGES.get(pkg_id, {})
    now = datetime.now(timezone.utc)
    if pkg.get("kind") == "subscription":
        end = now + timedelta(days=pkg["days"])
        await db.subscriptions.update_many({"company_id": tx["user_id"], "status": "active"}, {"$set": {"status": "renewed"}})
        await db.subscriptions.insert_one({
            "sub_id": f"sub_{uuid.uuid4().hex[:12]}",
            "company_id": tx["user_id"],
            "plan_type": pkg_id,
            "period": pkg["period"],
            "price": pkg["amount"],
            "status": "active",
            "start_date": now.isoformat(),
            "end_date": end.isoformat(),
            "renewal_date": end.isoformat(),
            "stripe_session_id": tx["session_id"],
            "created_at": now.isoformat(),
        })
    elif pkg.get("kind") == "boost":
        end = now + timedelta(days=pkg["days"])
        boost_field = "sponsored_until" if pkg["actor"] == "company" else "boosted_until"
        if tx.get("deal_id"):
            await db.deals.update_one({"deal_id": tx["deal_id"]}, {"$set": {boost_field: end.isoformat()}})
        await db.boost_orders.insert_one({
            "boost_id": f"boost_{uuid.uuid4().hex[:12]}",
            "user_id": tx["user_id"],
            "user_type": tx["user_role"],
            "deal_id": tx.get("deal_id"),
            "boost_type": "sponsored" if pkg["actor"] == "company" else "highlight",
            "price": pkg["amount"],
            "duration_days": pkg["days"],
            "start_date": now.isoformat(),
            "end_date": end.isoformat(),
            "status": "active",
            "session_id": tx["session_id"],
            "created_at": now.isoformat(),
        })
    await db.payment_transactions.update_one({"tx_id": tx["tx_id"]}, {"$set": {"fulfilled": True}})
    await db.revenue_logs.insert_one({
        "log_id": f"rev_{uuid.uuid4().hex[:10]}",
        "amount": tx["amount"],
        "currency": tx["currency"],
        "kind": tx["kind"],
        "user_id": tx["user_id"],
        "package_id": pkg_id,
        "at": now.isoformat(),
    })

@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request):
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transaction introuvable")
    if tx.get("payment_status") == "paid":
        return tx
    if not STRIPE_AVAILABLE:
        raise HTTPException(500, "Stripe indisponible")
    host_url = str(request.base_url).rstrip("/")
    stripe_co = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host_url}/api/webhook/stripe")
    try:
        res = await stripe_co.get_checkout_status(session_id)
    except Exception as e:
        logger.warning(f"Stripe status fetch failed for {session_id}: {e}")
        return tx
    new_status = res.payment_status
    upd = {"payment_status": new_status, "status": res.status}
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": upd})
    tx.update(upd)
    if new_status == "paid":
        await fulfill_transaction(tx)
    return tx

@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_AVAILABLE:
        return {"ok": False}
    body = await request.body()
    sig = request.headers.get("Stripe-Signature")
    host_url = str(request.base_url).rstrip("/")
    stripe_co = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host_url}/api/webhook/stripe")
    try:
        evt = await stripe_co.handle_webhook(body, sig)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False}
    if evt.payment_status == "paid":
        tx = await db.payment_transactions.find_one({"session_id": evt.session_id}, {"_id": 0})
        if tx and not tx.get("fulfilled"):
            await db.payment_transactions.update_one({"session_id": evt.session_id}, {"$set": {"payment_status": "paid", "status": "complete"}})
            tx["payment_status"] = "paid"
            await fulfill_transaction(tx)
    return {"ok": True}

# Admin monetization
@api.get("/admin/monetization")
async def admin_monetization(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin")
    active_subs = await db.subscriptions.find({"status": "active"}, {"_id": 0}).to_list(500)
    monthly = sum(1 for s in active_subs if s.get("period") == "monthly")
    yearly = sum(1 for s in active_subs if s.get("period") == "yearly")
    revenue = await db.revenue_logs.find({}, {"_id": 0}).to_list(2000)
    total = sum(r["amount"] for r in revenue)
    boost_student_rev = sum(r["amount"] for r in revenue if r["package_id"] == "boost_student")
    boost_company_rev = sum(r["amount"] for r in revenue if r["package_id"] == "boost_company")
    sub_rev = sum(r["amount"] for r in revenue if r["kind"] == "subscription")
    failed = await db.payment_transactions.count_documents({"payment_status": {"$in": ["failed", "expired"]}})
    canceled = await db.subscriptions.count_documents({"status": "canceled"})
    transactions = await db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return {
        "active_subs": len(active_subs),
        "monthly_subs": monthly,
        "yearly_subs": yearly,
        "total_revenue": total,
        "subscription_revenue": sub_rev,
        "boost_student_revenue": boost_student_rev,
        "boost_company_revenue": boost_company_rev,
        "failed_payments": failed,
        "canceled_subs": canceled,
        "transactions": transactions,
    }



# ============ EXTENSIONS v3: STORAGE, MULTI-SOURCE OFFERS, DOCS, GALLERY, SEARCH ============
from fastapi import UploadFile, File, Query, Header, Response as FResponse
import io

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = os.environ.get("APP_NAME", "stagiaireconnect")
_storage_key = None

def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_KEY:
        raise HTTPException(500, "Storage non configuré")
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key, "Content-Type": content_type},
                     data=data, timeout=120)
    r.raise_for_status()
    return r.json()

def get_object(path: str):
    key = init_storage()
    r = requests.get(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
        "webp": "image/webp", "pdf": "application/pdf",
        "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}

# Max sizes per file kind (bytes)
MAX_BYTES = {
    "image/jpeg": 8 * 1024 * 1024,
    "image/png": 8 * 1024 * 1024,
    "image/gif": 8 * 1024 * 1024,
    "image/webp": 8 * 1024 * 1024,
    "application/pdf": 15 * 1024 * 1024,
    "video/mp4": 50 * 1024 * 1024,
    "video/webm": 50 * 1024 * 1024,
    "video/quicktime": 50 * 1024 * 1024,
}
DEFAULT_MAX_BYTES = 10 * 1024 * 1024

@api.post("/upload")
async def upload_file(file: UploadFile = File(...), kind: str = "doc", user=Depends(get_current_user)):
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin").lower()
    if ext not in MIME:
        raise HTTPException(400, f"Type non supporté: {ext}")
    file_id = uuid.uuid4().hex
    path = f"{APP_NAME}/{user['user_id']}/{file_id}.{ext}"
    data = await file.read()
    limit = MAX_BYTES.get(MIME[ext], DEFAULT_MAX_BYTES)
    if len(data) > limit:
        raise HTTPException(400, f"Fichier trop volumineux (max {limit // (1024*1024)} Mo)")
    result = put_object(path, data, MIME[ext])
    doc = {
        "file_id": file_id,
        "user_id": user["user_id"],
        "storage_path": result["path"],
        "filename": file.filename,
        "content_type": MIME[ext],
        "size": result.get("size", len(data)),
        "kind": kind,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.files.insert_one(doc)
    doc.pop("_id", None)
    # Build a download URL the frontend can use
    backend_origin = os.environ.get("BACKEND_PUBLIC_URL", "")
    doc["url"] = f"/api/files/{file_id}"
    return doc

@api.get("/files/{file_id}")
async def download_file(file_id: str, request: Request, auth: Optional[str] = Query(None), authorization: Optional[str] = Header(None)):
    rec = await db.files.find_one({"file_id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Fichier introuvable")
    # Avatars, banners, post media, ad media, deal images are PUBLIC (loaded from <img> without auth)
    if rec.get("kind") in ("avatar", "banner", "post", "ad", "deal", "feed"):
        data, ct = get_object(rec["storage_path"])
        return FResponse(content=data, media_type=rec.get("content_type", ct))
    # Find document/photo reference if any
    student_doc = await db.student_documents.find_one({"file_id": file_id}, {"_id": 0})
    gallery_photo = await db.company_photos.find_one({"file_id": file_id}, {"_id": 0})
    # Gallery photos are public by default
    if gallery_photo:
        data, ct = get_object(rec["storage_path"])
        return FResponse(content=data, media_type=rec.get("content_type", ct))
    # For documents with visibility, validate access
    if student_doc:
        owner_id = student_doc["user_id"]
        visibility = student_doc.get("visibility", "after_application")
        if visibility == "public":
            data, ct = get_object(rec["storage_path"])
            return FResponse(content=data, media_type=rec.get("content_type", ct))
        # Need authenticated caller
        try:
            req_user = await get_current_user(request)
        except HTTPException:
            raise HTTPException(401, "Authentification requise pour ce document")
        if req_user["user_id"] == owner_id:
            data, ct = get_object(rec["storage_path"])
            return FResponse(content=data, media_type=rec.get("content_type", ct))
        if visibility == "connected":
            has_contact = await db.contacts.find_one({"$or": [
                {"user_a": owner_id, "user_b": req_user["user_id"]},
                {"user_a": req_user["user_id"], "user_b": owner_id},
            ]})
            if not has_contact:
                raise HTTPException(403, "Document réservé aux contacts")
        elif visibility == "after_application":
            ap = await db.applications.find_one({"candidate_id": owner_id, "company_id": req_user["user_id"]})
            if not ap:
                raise HTTPException(403, "Document accessible après candidature")
        else:  # private
            raise HTTPException(403, "Document privé")
        data, ct = get_object(rec["storage_path"])
        return FResponse(content=data, media_type=rec.get("content_type", ct))
    # No reference: only file owner can download
    try:
        req_user = await get_current_user(request)
        if req_user["user_id"] != rec["user_id"]:
            raise HTTPException(403, "Accès refusé")
    except HTTPException:
        raise HTTPException(401, "Authentification requise")
    data, ct = get_object(rec["storage_path"])
    return FResponse(content=data, media_type=rec.get("content_type", ct))

# ============ STUDENT DOCUMENTS ============
@api.post("/me/documents")
async def add_doc(body: dict, user=Depends(get_current_user)):
    """Register a document (file_id from /upload) under student's profile."""
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    doc_id = f"d_{uuid.uuid4().hex[:10]}"
    entry = {
        "doc_id": doc_id,
        "user_id": user["user_id"],
        "file_id": body.get("file_id"),
        "filename": body.get("filename", "document"),
        "doc_type": body.get("doc_type", "cv"),  # cv, lettre, convention, portfolio, autre
        "visibility": body.get("visibility", "after_application"),  # private, connected, after_application, public
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.student_documents.insert_one(entry)
    entry.pop("_id", None)
    return entry

@api.get("/users/{user_id}/documents")
async def list_user_documents(user_id: str, requester=Depends(get_optional_user)):
    docs = await db.student_documents.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    if requester and requester["user_id"] == user_id:
        return docs  # owner sees all
    # Determine accessible docs
    out = []
    has_contact = False
    has_app = False
    if requester:
        ct = await db.contacts.find_one({"$or": [
            {"user_a": user_id, "user_b": requester["user_id"]},
            {"user_a": requester["user_id"], "user_b": user_id},
        ]})
        has_contact = bool(ct)
        ap = await db.applications.find_one({"candidate_id": user_id, "company_id": requester["user_id"]})
        has_app = bool(ap)
    for d in docs:
        v = d.get("visibility", "after_application")
        ok = v == "public" or (v == "connected" and has_contact) or (v == "after_application" and has_app)
        if ok:
            out.append(d)
    return out

@api.delete("/me/documents/{doc_id}")
async def delete_doc(doc_id: str, user=Depends(get_current_user)):
    await db.student_documents.delete_one({"doc_id": doc_id, "user_id": user["user_id"]})
    return {"ok": True}

# ============ COMPANY GALLERY ============
@api.post("/me/gallery")
async def add_photo(body: dict, user=Depends(get_current_user)):
    if user["role"] != "company":
        raise HTTPException(403, "Entreprises uniquement")
    pid = f"p_{uuid.uuid4().hex[:10]}"
    entry = {
        "photo_id": pid,
        "user_id": user["user_id"],
        "file_id": body.get("file_id"),
        "url": body.get("url"),  # accepts direct URL too
        "title": body.get("title", "Photo"),
        "is_hidden": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.company_photos.insert_one(entry)
    entry.pop("_id", None)
    return entry

@api.get("/users/{user_id}/gallery")
async def get_gallery(user_id: str):
    photos = await db.company_photos.find({"user_id": user_id, "is_hidden": {"$ne": True}}, {"_id": 0}).to_list(100)
    return photos

@api.delete("/me/gallery/{photo_id}")
async def remove_photo(photo_id: str, user=Depends(get_current_user)):
    await db.company_photos.delete_one({"photo_id": photo_id, "user_id": user["user_id"]})
    return {"ok": True}

# ============ EXTENDED OFFERS: source filter ============
@api.get("/offer-sources")
async def list_sources():
    return {
        "sources": [
            {"id": "StageConnect", "label": "StageEtudiant", "internal": True},
            {"id": "HelloWork", "label": "HelloWork", "internal": False},
            {"id": "LinkedIn", "label": "LinkedIn", "internal": False},
            {"id": "Indeed", "label": "Indeed", "internal": False},
            {"id": "WelcomeToTheJungle", "label": "Welcome to the Jungle", "internal": False},
            {"id": "FranceTravail", "label": "France Travail", "internal": False},
            {"id": "JobTeaser", "label": "JobTeaser", "internal": False},
            {"id": "StudentJob", "label": "StudentJob", "internal": False},
            {"id": "LEtudiant", "label": "L'Étudiant", "internal": False},
            {"id": "Apec", "label": "Apec", "internal": False},
            {"id": "Meteojob", "label": "Meteojob", "internal": False},
            {"id": "Monster", "label": "Monster", "internal": False},
            {"id": "TalentCom", "label": "Talent.com", "internal": False},
            {"id": "La Bonne Alternance", "label": "La Bonne Alternance", "internal": False, "official": True},
        ]
    }

# ============ SAVED OFFERS ============
@api.post("/saved-offers/{offer_id}")
async def save_offer(offer_id: str, user=Depends(get_current_user)):
    existing = await db.saved_offers.find_one({"user_id": user["user_id"], "offer_id": offer_id})
    if existing:
        await db.saved_offers.delete_one({"user_id": user["user_id"], "offer_id": offer_id})
        return {"saved": False}
    await db.saved_offers.insert_one({
        "saved_id": f"s_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"], "offer_id": offer_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"saved": True}

@api.get("/saved-offers")
async def my_saved_offers(user=Depends(get_current_user)):
    saved = await db.saved_offers.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    ids = [s["offer_id"] for s in saved]
    offers = await db.offers.find({"offer_id": {"$in": ids}}, {"_id": 0}).to_list(200)
    return offers

# ============ APPLICATIONS DETAIL + EXTENSIONS ============
@api.get("/applications/{app_id}")
async def get_application(app_id: str, user=Depends(get_current_user)):
    a = await db.applications.find_one({"app_id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Introuvable")
    if user["user_id"] not in (a["candidate_id"], a["company_id"]) and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    if user["role"] == "company" and a["company_id"] == user["user_id"] and not a.get("viewed_at"):
        await db.applications.update_one({"app_id": app_id}, {"$set": {"viewed_at": datetime.now(timezone.utc).isoformat(), "status": "vue" if a["status"] == "envoyee" else a["status"]}})
        a["viewed_at"] = datetime.now(timezone.utc).isoformat()
    candidate = await db.users.find_one({"user_id": a["candidate_id"]}, {"_id": 0, "password": 0})
    offer = await db.offers.find_one({"offer_id": a["offer_id"]}, {"_id": 0})
    documents = []
    if user["role"] == "company" and a["company_id"] == user["user_id"]:
        documents = await db.student_documents.find({"user_id": a["candidate_id"]}, {"_id": 0}).to_list(20)
    return {"application": a, "candidate": candidate, "offer": offer, "documents": documents}

@api.delete("/applications/{app_id}")
async def withdraw_application(app_id: str, user=Depends(get_current_user)):
    a = await db.applications.find_one({"app_id": app_id})
    if not a or a["candidate_id"] != user["user_id"]:
        raise HTTPException(403, "Interdit")
    await db.applications.update_one({"app_id": app_id}, {"$set": {"status": "retiree"}})
    return {"ok": True}

@api.post("/applications/{app_id}/note")
async def application_note(app_id: str, body: dict, user=Depends(get_current_user)):
    a = await db.applications.find_one({"app_id": app_id})
    if not a or a["company_id"] != user["user_id"]:
        raise HTTPException(403, "Interdit")
    await db.applications.update_one({"app_id": app_id}, {"$set": {"company_note": body.get("note", "")}})
    return {"ok": True}

# Override applications status update to support new statuses
@api.patch("/applications/{app_id}/status")
async def set_application_status(app_id: str, body: dict, user=Depends(get_current_user)):
    a = await db.applications.find_one({"app_id": app_id})
    if not a:
        raise HTTPException(404, "Introuvable")
    if a["company_id"] != user["user_id"] and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    status = body.get("status")
    allowed = {"vue", "en_analyse", "entretien_propose", "acceptee", "refusee", "archivee",
               "internship_obtained", "apprenticeship_obtained", "contract_signed"}
    if status not in allowed:
        raise HTTPException(400, "Statut invalide")
    await db.applications.update_one({"app_id": app_id}, {"$set": {"status": status}})
    await notify(a["candidate_id"], "application_status", f"Votre candidature \"{a['offer_title']}\" est maintenant: {status}", "/dashboard")
    return {"ok": True}

# ============ SEARCH STUDENTS (by companies) ============
@api.get("/search/students")
async def search_students(
    q: Optional[str] = None,
    level: Optional[str] = None,
    domain: Optional[str] = None,
    city: Optional[str] = None,
    region: Optional[str] = None,
    contract_type: Optional[str] = None,
    student_status: Optional[str] = None,
    skill: Optional[str] = None,
    limit: int = 50,
    user=Depends(get_current_user),
):
    if user["role"] not in ("company", "admin"):
        raise HTTPException(403, "Réservé aux entreprises")
    query = {"role": "candidate"}
    if q:
        query["$or"] = [{"name": {"$regex": q, "$options": "i"}}]
    if level: query["profile.level"] = level
    if domain: query["profile.domain"] = {"$regex": domain, "$options": "i"}
    if city: query["profile.city"] = {"$regex": city, "$options": "i"}
    if region: query["profile.region"] = region
    if contract_type: query["profile.contract_type"] = contract_type
    if student_status: query["profile.status"] = student_status
    if skill: query["profile.skills"] = {"$regex": skill, "$options": "i"}
    users = await db.users.find(query, {"_id": 0, "password": 0}).limit(limit).to_list(limit)
    return users

# ============ CONTACT EXTENSIONS — moved to routes/contacts.py ============

# ============ MASSIVE SEED v3 ============
@api.post("/seed-v3")
async def seed_v3(force: bool = False):
    if not force and await db.offers.count_documents({}) > 50:
        return {"ok": True, "msg": "Déjà peuplé"}
    # Clean only offers (keep users, deals, etc. from earlier seeds intact)
    await db.offers.delete_many({})
    await db.users.delete_many({"role": "company", "user_id": {"$regex": "^user_cobig"}})

    SOURCES = ["StageConnect", "HelloWork", "LinkedIn", "Indeed", "WelcomeToTheJungle", "FranceTravail",
               "JobTeaser", "StudentJob", "LEtudiant", "Apec", "Meteojob", "Monster", "TalentCom"]
    SOURCE_URLS = {
        "HelloWork": "https://www.hellowork.com",
        "LinkedIn": "https://www.linkedin.com/jobs",
        "Indeed": "https://fr.indeed.com",
        "WelcomeToTheJungle": "https://www.welcometothejungle.com",
        "FranceTravail": "https://candidat.francetravail.fr",
        "JobTeaser": "https://www.jobteaser.com",
        "StudentJob": "https://www.studentjob.fr",
        "LEtudiant": "https://www.letudiant.fr/jobsstages.html",
        "Apec": "https://www.apec.fr",
        "Meteojob": "https://www.meteojob.com",
        "Monster": "https://www.monster.fr",
        "TalentCom": "https://fr.talent.com",
    }
    REGIONS = [
        ("Île-de-France", ["Paris", "Versailles", "Nanterre", "Saint-Denis", "Boulogne-Billancourt"]),
        ("Auvergne-Rhône-Alpes", ["Lyon", "Grenoble", "Saint-Étienne", "Clermont-Ferrand", "Annecy"]),
        ("Nouvelle-Aquitaine", ["Bordeaux", "Poitiers", "Limoges", "La Rochelle", "Pau"]),
        ("Occitanie", ["Toulouse", "Montpellier", "Nîmes", "Perpignan"]),
        ("Hauts-de-France", ["Lille", "Amiens", "Roubaix", "Tourcoing"]),
        ("Provence-Alpes-Côte d'Azur", ["Marseille", "Nice", "Aix-en-Provence", "Toulon", "Cannes"]),
        ("Grand Est", ["Strasbourg", "Reims", "Metz", "Nancy"]),
        ("Pays de la Loire", ["Nantes", "Angers", "Le Mans"]),
        ("Bretagne", ["Rennes", "Brest", "Quimper", "Lorient"]),
        ("Normandie", ["Rouen", "Caen", "Le Havre"]),
        ("Bourgogne-Franche-Comté", ["Dijon", "Besançon", "Belfort"]),
        ("Centre-Val de Loire", ["Tours", "Orléans", "Bourges"]),
        ("Corse", ["Ajaccio", "Bastia"]),
    ]
    SECTORS = ["Informatique", "Cybersécurité", "Développement web", "Industrie", "Nucléaire", "Mécanique",
               "Électricité", "Maintenance", "Commerce", "Vente", "Logistique", "Transport", "Restauration",
               "Hôtellerie", "Bâtiment", "Marketing", "Communication", "Comptabilité", "RH", "Santé",
               "Social", "Environnement", "Énergie"]
    PREFIXES = ["Nova", "Alpha", "Beta", "Tech", "Smart", "Bright", "Prime", "Atlas", "Quantum", "Pixel",
                "Cyber", "Green", "Pulse", "Core", "Edge", "Vector", "Solar", "Eco", "Lumen", "Spark"]
    SUFFIXES = ["Lab", "Group", "Tech", "Industries", "Conseil", "Solutions", "Systems", "Studio", "Works", "Network"]
    LOGOS = [
        "https://images.unsplash.com/photo-1770012977129-19f856a1f935?w=200",
        "https://images.unsplash.com/photo-1761044591996-7a05341a3e12?w=200",
        "https://images.unsplash.com/photo-1770210217380-d78a69acdc77?w=200",
    ]
    BANNERS = [
        "https://images.unsplash.com/photo-1758691736975-9f7f643d178e?w=1200",
        "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200",
        "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200",
    ]
    JOB_TEMPLATES = [
        ("Développeur Full-Stack", "Informatique", ["JavaScript", "React", "Node.js"]),
        ("Développeur Frontend", "Développement web", ["React", "TypeScript", "CSS"]),
        ("Développeur Backend", "Informatique", ["Python", "FastAPI", "SQL"]),
        ("Analyste Cybersécurité", "Cybersécurité", ["Pentest", "Linux", "SIEM"]),
        ("Data Analyst", "Informatique", ["SQL", "Python", "Excel"]),
        ("Ingénieur DevOps", "Informatique", ["Docker", "Kubernetes", "AWS"]),
        ("Technicien de maintenance", "Maintenance", ["Mécanique", "Hydraulique", "Diagnostic"]),
        ("Ingénieur Mécanique", "Mécanique", ["CAO", "SolidWorks", "Calcul"]),
        ("Technicien Électricité", "Électricité", ["Habilitation", "Câblage", "Schémas"]),
        ("Chargé de communication", "Communication", ["Réseaux sociaux", "Rédaction", "Photoshop"]),
        ("Chargé de marketing digital", "Marketing", ["SEO", "Google Ads", "Analytics"]),
        ("Assistant Comptable", "Comptabilité", ["Sage", "Excel", "Saisie"]),
        ("Chargé de recrutement", "RH", ["Sourcing", "Entretiens", "LinkedIn"]),
        ("Commercial B2B", "Commerce", ["Prospection", "Négociation", "CRM"]),
        ("Conseiller de vente", "Vente", ["Relation client", "Conseil", "Encaissement"]),
        ("Cariste / Préparateur de commandes", "Logistique", ["CACES", "Rigueur", "Inventaire"]),
        ("Chauffeur livreur", "Transport", ["Permis B", "Itinéraires"]),
        ("Serveur / Serveuse", "Restauration", ["Service", "Tenue", "Sourire"]),
        ("Réceptionniste hôtellerie", "Hôtellerie", ["Anglais", "Accueil", "Réservations"]),
        ("Aide-soignant", "Santé", ["Empathie", "Soins", "Hygiène"]),
        ("Éducateur spécialisé", "Social", ["Écoute", "Animations", "Accompagnement"]),
        ("Technicien environnement", "Environnement", ["Mesures", "Reporting", "Normes ISO"]),
        ("Ingénieur Énergies renouvelables", "Énergie", ["Photovoltaïque", "Éolien", "ENR"]),
        ("Conducteur de travaux", "Bâtiment", ["Planning", "Sécurité", "Lecture de plans"]),
        ("Designer UX/UI", "Développement web", ["Figma", "Wireframe", "Prototype"]),
        ("Product Owner Junior", "Informatique", ["Agile", "Scrum", "User stories"]),
    ]

    import random
    random.seed(42)

    company_docs = []
    for i in range(110):
        region, cities = random.choice(REGIONS)
        city = random.choice(cities)
        sector = random.choice(SECTORS)
        name = f"{random.choice(PREFIXES)}{random.choice(SUFFIXES)}{i:03d}"
        cid = f"user_cobig{i:04d}"
        doc = {
            "user_id": cid,
            "email": f"hr@{name.lower()}.fr",
            "password": hash_password("Demo1234!"),
            "name": name,
            "role": "company",
            "profile": {
                "company_name": name,
                "logo": LOGOS[i % len(LOGOS)],
                "banner": BANNERS[i % len(BANNERS)],
                "sector": sector,
                "size": random.choice(["1-10", "11-50", "51-200", "201-500", "500+"]),
                "city": city, "region": region,
                "address": f"{random.randint(1, 200)} rue {random.choice(['de la République', 'Voltaire', 'Pasteur', 'Hugo'])}",
                "siret": f"{random.randint(100000000, 999999999)}00012",
                "website": f"https://{name.lower()}.fr",
                "description": f"{name} est une entreprise leader dans le secteur {sector.lower()}, basée à {city}. Nous recrutons régulièrement stagiaires et alternants.",
                "phone": f"01 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                "pro_email": f"hr@{name.lower()}.fr",
                "recruiting_domains": [sector],
                "verified": i % 3 != 0,
                "company_status": random.choice(["recrute_stagiaire", "recrute_alternant", "recrute_les_deux", "pas_de_recrutement"]),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        company_docs.append(doc)
    await db.users.insert_many(company_docs)

    # Generate 320 offers (mix internal + external)
    offers = []
    for i in range(320):
        template = random.choice(JOB_TEMPLATES)
        title, dom, skills = template
        co = random.choice(company_docs)
        region = co["profile"]["region"]
        city = co["profile"]["city"]
        # Sometimes switch city to a random one in same region for variety
        if random.random() < 0.4:
            for r, cities in REGIONS:
                if r == region:
                    city = random.choice(cities)
                    break
        source = random.choice(SOURCES)
        ct = random.choice(["stage", "alternance"])
        is_internal = source == "StageConnect"
        offer = {
            "offer_id": f"off_big_{i:04d}",
            "company_id": co["user_id"] if is_internal else None,
            "company_name": co["profile"]["company_name"],
            "company_logo": co["profile"]["logo"],
            "verified": co["profile"]["verified"],
            "source": source,
            "external_url": SOURCE_URLS.get(source, "") + f"/offre-{i}" if not is_internal else None,
            "title": title,
            "contract_type": ct,
            "domain": dom,
            "city": city,
            "region": region,
            "remote": random.random() < 0.3,
            "duration": "6 mois" if ct == "stage" else random.choice(["1 an", "2 ans"]),
            "rhythm": "3j entreprise / 2j école" if ct == "alternance" else None,
            "start_date": random.choice(["Septembre 2026", "Janvier 2026", "Mars 2026", "Dès que possible"]),
            "level": random.choice(["Bac+2", "Bac+3", "Bac+5"]),
            "skills": skills,
            "description": f"Nous recherchons un(e) {title} motivé(e) pour rejoindre notre équipe à {city}. Vous travaillerez sur des projets stimulants dans le secteur {dom.lower()}.",
            "profile": "Étudiant(e) en formation pertinente, motivé(e), avec une appétence pour le domaine.",
            "benefits": random.choice(["Tickets restaurant, télétravail partiel, mutuelle", "Prime de fin d'année, RTT, formation continue", "Environnement startup, locaux modernes, équipe jeune"]),
            "salary": "Gratification 600€" if ct == "stage" else f"{random.choice(['800', '1000', '1200', '1400'])}€ / mois",
            "views": random.randint(0, 500),
            "status": random.choice(["active", "active", "active", "expiree"]),
            "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 60))).isoformat(),
        }
        offers.append(offer)
    await db.offers.insert_many(offers)
    return {"ok": True, "companies_added": len(company_docs), "offers_added": len(offers)}



# ============ PHASE B: GEOCODING + DISTANCE SEARCH ============
# Static mapping of major French cities → coordinates (lat, lng)
CITY_COORDS = {
    "paris": (48.8566, 2.3522), "marseille": (43.2965, 5.3698), "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442), "nice": (43.7102, 7.2620), "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521), "montpellier": (43.6108, 3.8767), "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573), "rennes": (48.1173, -1.6778), "reims": (49.2583, 4.0317),
    "saint-étienne": (45.4397, 4.3872), "toulon": (43.1242, 5.9280), "le havre": (49.4944, 0.1079),
    "grenoble": (45.1885, 5.7245), "dijon": (47.3220, 5.0415), "angers": (47.4784, -0.5632),
    "nîmes": (43.8367, 4.3601), "villeurbanne": (45.7720, 4.8902), "saint-denis": (48.9362, 2.3574),
    "le mans": (48.0061, 0.1996), "aix-en-provence": (43.5297, 5.4474), "clermont-ferrand": (45.7772, 3.0870),
    "brest": (48.3905, -4.4860), "tours": (47.3941, 0.6848), "amiens": (49.8941, 2.2958),
    "limoges": (45.8336, 1.2611), "annecy": (45.8992, 6.1294), "perpignan": (42.6886, 2.8948),
    "boulogne-billancourt": (48.8352, 2.2412), "besançon": (47.2378, 6.0241), "orléans": (47.9029, 1.9039),
    "metz": (49.1193, 6.1757), "rouen": (49.4432, 1.0993), "mulhouse": (47.7508, 7.3359),
    "caen": (49.1829, -0.3707), "nancy": (48.6921, 6.1844), "poitiers": (46.5802, 0.3404),
    "versailles": (48.8049, 2.1204), "la rochelle": (46.1591, -1.1517), "pau": (43.2951, -0.3708),
    "bourges": (47.0810, 2.3988), "ajaccio": (41.9192, 8.7386), "bastia": (42.7028, 9.4503),
    "belfort": (47.6379, 6.8628), "quimper": (47.9960, -4.0978), "lorient": (47.7484, -3.3702),
    "saint-denis (réunion)": (-20.8823, 55.4504), "cannes": (43.5528, 7.0174), "tourcoing": (50.7235, 3.1602),
    "roubaix": (50.6927, 3.1746), "nanterre": (48.8924, 2.2069),
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def get_coords(city: Optional[str]):
    if not city:
        return None
    return CITY_COORDS.get(city.strip().lower())

@api.get("/cities")
async def list_cities():
    """Return list of geocodable cities for frontend autocomplete."""
    return {"cities": sorted([c.title() for c in CITY_COORDS.keys()])}

@api.get("/offers-nearby")
async def offers_nearby(city: str, distance_km: float = 50, limit: int = 200,
                        contract_type: Optional[str] = None, source: Optional[str] = None):
    coords = get_coords(city)
    if not coords:
        raise HTTPException(404, f"Ville inconnue: {city}. Utilisez /api/cities pour la liste.")
    lat0, lon0 = coords
    query = {}
    if contract_type: query["contract_type"] = contract_type
    if source: query["source"] = source
    offers = await db.offers.find(query, {"_id": 0}).to_list(2000)
    result = []
    for o in offers:
        oc = get_coords(o.get("city"))
        if not oc:
            continue
        d = haversine(lat0, lon0, oc[0], oc[1])
        if d <= distance_km:
            o["distance_km"] = round(d, 1)
            result.append(o)
    result.sort(key=lambda x: x["distance_km"])
    return result[:limit]

@api.get("/search/students-nearby")
async def students_nearby(city: str, distance_km: float = 50, limit: int = 100,
                          user=Depends(get_current_user)):
    if user["role"] not in ("company", "admin"):
        raise HTTPException(403, "Réservé aux entreprises")
    coords = get_coords(city)
    if not coords:
        raise HTTPException(404, f"Ville inconnue: {city}")
    lat0, lon0 = coords
    students = await db.users.find({"role": "candidate"}, {"_id": 0, "password": 0}).to_list(2000)
    result = []
    for s in students:
        sc = get_coords(s.get("profile", {}).get("city"))
        if not sc:
            continue
        d = haversine(lat0, lon0, sc[0], sc[1])
        if d <= distance_km:
            s["distance_km"] = round(d, 1)
            result.append(s)
    result.sort(key=lambda x: x["distance_km"])
    return result[:limit]

# ============ PHASE B: WEBSOCKET REAL-TIME MESSAGING ============
class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.online: Set[str] = set()

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id].add(ws)
        self.online.add(user_id)
        await self.broadcast_presence(user_id, True)

    def disconnect(self, user_id: str, ws: WebSocket):
        if ws in self.active[user_id]:
            self.active[user_id].remove(ws)
        if not self.active[user_id]:
            self.online.discard(user_id)

    async def send_to(self, user_id: str, payload: dict):
        dead = []
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_text(_json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active[user_id].discard(ws)

    async def broadcast_presence(self, user_id: str, online: bool):
        # Notify all this user's contacts about presence change
        contacts = await db.contacts.find({"$or": [{"user_a": user_id}, {"user_b": user_id}]}, {"_id": 0}).to_list(500)
        for c in contacts:
            peer = c["user_b"] if c["user_a"] == user_id else c["user_a"]
            await self.send_to(peer, {"type": "presence", "user_id": user_id, "online": online})

manager = ConnectionManager()

def verify_ws_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get("user_id")
    except Exception:
        return None

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    user_id = verify_ws_token(token)
    if not user_id:
        # Try session token
        sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
        if sess:
            user_id = sess.get("user_id")
    if not user_id:
        await websocket.close(code=1008)
        return
    await manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = _json.loads(raw)
            except Exception:
                continue
            kind = data.get("type")
            if kind == "typing":
                to_id = data.get("to_user_id")
                if to_id:
                    await manager.send_to(to_id, {"type": "typing", "from_id": user_id, "is_typing": data.get("is_typing", True)})
            elif kind == "ping":
                await websocket.send_text(_json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
        await manager.broadcast_presence(user_id, False)
    except Exception as e:
        logger.warning(f"WS error: {e}")
        manager.disconnect(user_id, websocket)
        await manager.broadcast_presence(user_id, False)

@api.get("/presence")
async def presence(user=Depends(get_current_user)):
    """Return list of online contact user_ids."""
    contacts = await db.contacts.find({"$or": [{"user_a": user["user_id"]}, {"user_b": user["user_id"]}]}, {"_id": 0}).to_list(500)
    peer_ids = [c["user_b"] if c["user_a"] == user["user_id"] else c["user_a"] for c in contacts]
    online = [pid for pid in peer_ids if pid in manager.online]
    return {"online": online}

# Hook into send_message to push real-time notifications
async def push_new_message_event(msg: dict):
    payload = {"type": "message", "message": msg}
    await manager.send_to(msg["to_id"], payload)
    await manager.send_to(msg["from_id"], payload)

# Wrap the existing /messages POST to push websocket events without breaking the API
@api.post("/messages-rt")
async def send_message_rt(data: MessageIn, user=Depends(get_current_user)):
    other = await db.users.find_one({"user_id": data.to_user_id}, {"_id": 0})
    if not other:
        raise HTTPException(404, "Destinataire introuvable")
    pair = sorted([user["user_id"], data.to_user_id])
    conv_id = f"conv_{pair[0][-6:]}_{pair[1][-6:]}"
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    attachments = [a.model_dump() for a in (data.attachments or [])]
    if data.attachment and not attachments:
        attachments = [{"type": "file", "url": data.attachment, "file_id": None, "filename": None, "mime": None, "size": None}]
    doc = {
        "message_id": msg_id, "conv_id": conv_id,
        "from_id": user["user_id"], "from_name": user["name"],
        "to_id": data.to_user_id, "to_name": other["name"],
        "content": data.content, "attachment": data.attachment,
        "attachments": attachments,
        "read": False, "created_at": now,
    }
    await db.messages.insert_one(doc)
    doc.pop("_id", None)
    await db.conversations.update_one(
        {"conv_id": conv_id},
        {"$set": {"conv_id": conv_id, "participants": pair,
                  "last_message": data.content or ("📎 " + (attachments[0]["filename"] or "Pièce jointe") if attachments else ""),
                  "last_at": now}},
        upsert=True,
    )
    await notify(data.to_user_id, "message", f"Nouveau message de {user['name']}", "/messages", {"user_id": user["user_id"], "name": user["name"]})
    await push_new_message_event(doc)
    return doc

# ============ PHASE B: EXTERNAL API CONNECTOR FRAMEWORK ============
# Structure prête à recevoir de vraies API. Pour l'instant, génère des données
# simulées avec une signature commune. Plus tard: brancher de vraies API.

class ExternalConnector:
    """Base class for external offer sources."""
    name = "Unknown"
    enabled = False
    api_endpoint = None

    async def fetch(self, query: str = "", location: str = "", limit: int = 20) -> List[dict]:
        """Fetch external offers. Returns list of offer dicts in our canonical format."""
        raise NotImplementedError

    def _make_offer(self, idx, title, city, region, contract_type="stage"):
        return {
            "offer_id": f"ext_{self.name.lower()}_{idx}_{uuid.uuid4().hex[:6]}",
            "company_id": None,
            "company_name": f"Entreprise {self.name} #{idx}",
            "company_logo": None,
            "verified": False,
            "source": self.name,
            "external_url": f"{self.api_endpoint}/offre/{idx}" if self.api_endpoint else None,
            "title": title, "contract_type": contract_type,
            "domain": "Multi-domaine", "city": city, "region": region,
            "remote": idx % 4 == 0, "duration": "6 mois" if contract_type == "stage" else "1 an",
            "rhythm": None, "start_date": "À convenir",
            "level": "Bac+3", "skills": ["Polyvalence", "Motivation"],
            "description": f"Offre issue de {self.name}. Pour postuler, ouvrez le site source.",
            "profile": "Étudiant motivé(e)", "benefits": "Selon entreprise",
            "salary": "Selon profil", "views": 0,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

class HelloWorkConnector(ExternalConnector):
    name = "HelloWork"; api_endpoint = "https://www.hellowork.com"
    async def fetch(self, query="", location="", limit=20):
        # TODO: HelloWork doesn't expose a public API — partner contract required.
        # Currently returns simulated batch. When real API available, swap this.
        return [self._make_offer(i, f"Stage {query or 'Marketing'}", location or "Paris", "Île-de-France") for i in range(limit)]

class FranceTravailConnector(ExternalConnector):
    name = "FranceTravail"; api_endpoint = "https://candidat.francetravail.fr"
    async def fetch(self, query="", location="", limit=20):
        # France Travail expose une API officielle (sur demande) — structure prête.
        return [self._make_offer(i, f"Alternance {query or 'Commerce'}", location or "Lyon", "Auvergne-Rhône-Alpes", "alternance") for i in range(limit)]

CONNECTORS = {
    "HelloWork": HelloWorkConnector(),
    "FranceTravail": FranceTravailConnector(),
}

@api.post("/admin/refresh-external")
async def refresh_external(source: str = "HelloWork", query: str = "", location: str = "Paris", limit: int = 20, user=Depends(get_current_user)):
    """Admin endpoint to (re)fetch external offers and persist them."""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin uniquement")
    conn = CONNECTORS.get(source)
    if not conn:
        raise HTTPException(400, f"Source non supportée: {source}. Disponibles: {list(CONNECTORS.keys())}")
    fetched = await conn.fetch(query=query, location=location, limit=limit)
    # Idempotent insert: skip if offer_id exists
    inserted = 0
    for off in fetched:
        existing = await db.offers.find_one({"offer_id": off["offer_id"]})
        if not existing:
            await db.offers.insert_one(off)
            inserted += 1
    return {"ok": True, "source": source, "fetched": len(fetched), "inserted": inserted}

@api.get("/admin/external-connectors")
async def list_connectors(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin uniquement")
    return {
        "connectors": [
            {"name": c.name, "endpoint": c.api_endpoint, "enabled": c.enabled, "status": "simulation_only" if not c.enabled else "live"}
            for c in CONNECTORS.values()
        ]
    }



# ============ ITERATION 5: AVATAR/BANNER UPLOAD + COMPRESSION ============
from PIL import Image

def compress_image(data: bytes, max_w: int, max_h: int, quality: int = 82, fmt: str = "JPEG") -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format=fmt, quality=quality, optimize=True)
    return out.getvalue()

@api.post("/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user=Depends(get_current_user)):
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image trop grande (max 10 Mo)")
    try:
        compressed = compress_image(raw, 512, 512, quality=85)
    except Exception:
        raise HTTPException(400, "Image invalide")
    file_id = uuid.uuid4().hex
    path = f"{APP_NAME}/{user['user_id']}/avatar_{file_id}.jpg"
    put_object(path, compressed, "image/jpeg")
    await db.files.insert_one({
        "file_id": file_id, "user_id": user["user_id"],
        "storage_path": path, "filename": "avatar.jpg",
        "content_type": "image/jpeg", "size": len(compressed),
        "kind": "avatar", "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    avatar_url = f"/api/files/{file_id}"
    profile = user.get("profile", {})
    key = "logo" if user["role"] == "company" else "avatar"
    profile[key] = avatar_url
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"profile": profile}})
    # Cascade to authored content
    await db.posts.update_many({"author_id": user["user_id"]}, {"$set": {"author_avatar": avatar_url}})
    await db.comments.update_many({"author_id": user["user_id"]}, {"$set": {"author_avatar": avatar_url}})
    if user["role"] == "candidate":
        await db.applications.update_many({"candidate_id": user["user_id"]}, {"$set": {"candidate_avatar": avatar_url}})
    if user["role"] == "company":
        await db.offers.update_many({"company_id": user["user_id"]}, {"$set": {"company_logo": avatar_url}})
    return {"url": avatar_url, "file_id": file_id}

@api.post("/me/banner")
async def upload_banner(file: UploadFile = File(...), user=Depends(get_current_user)):
    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "Image trop grande (max 12 Mo)")
    try:
        compressed = compress_image(raw, 1600, 600, quality=82)
    except Exception:
        raise HTTPException(400, "Image invalide")
    file_id = uuid.uuid4().hex
    path = f"{APP_NAME}/{user['user_id']}/banner_{file_id}.jpg"
    put_object(path, compressed, "image/jpeg")
    await db.files.insert_one({
        "file_id": file_id, "user_id": user["user_id"],
        "storage_path": path, "filename": "banner.jpg",
        "content_type": "image/jpeg", "size": len(compressed),
        "kind": "banner", "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    banner_url = f"/api/files/{file_id}"
    profile = user.get("profile", {})
    profile["banner"] = banner_url
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"profile": profile}})
    return {"url": banner_url, "file_id": file_id}

@api.delete("/me/avatar")
async def remove_avatar(user=Depends(get_current_user)):
    profile = user.get("profile", {})
    key = "logo" if user["role"] == "company" else "avatar"
    profile.pop(key, None)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"profile": profile}})
    return {"ok": True}

@api.delete("/me/banner")
async def remove_banner(user=Depends(get_current_user)):
    profile = user.get("profile", {})
    profile.pop("banner", None)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"profile": profile}})
    return {"ok": True}

# ============ ITERATION 5: CASCADING UPDATES FOR COMPANY NAME ============
@api.put("/profile-v2")
async def update_profile_cascade(data: dict, user=Depends(get_current_user)):
    """Like /profile PUT, but cascades critical fields (name) to authored content.
    Whitelists allowed fields to prevent privilege escalation (e.g. self-granting premium)."""
    CANDIDATE_FIELDS = {
        "first_name", "last_name", "title", "avatar", "banner", "city", "region",
        "school", "level", "domain", "contract_type", "duration", "availability",
        "skills", "experiences", "description", "cv_url", "portfolio_url",
        "linkedin_url", "status", "mobile",
    }
    COMPANY_FIELDS = {
        "company_name", "logo", "banner", "sector", "size", "address", "city",
        "region", "siret", "website", "description", "hr_contact", "pro_email",
        "phone", "recruiting_domains", "company_status",
        # Phase B — official directory enrichment
        "siren", "postal_code", "naf_code", "siret_verified", "siret_verified_at",
    }
    allowed = COMPANY_FIELDS if user["role"] == "company" else CANDIDATE_FIELDS
    profile = user.get("profile", {})
    safe_updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    profile.update(safe_updates)
    set_doc = {"profile": profile}
    if user["role"] == "company":
        new_name = profile.get("company_name")
        if new_name and new_name != user.get("name"):
            set_doc["name"] = new_name
            await db.offers.update_many({"company_id": user["user_id"]}, {"$set": {"company_name": new_name}})
            await db.applications.update_many({"company_id": user["user_id"]}, {"$set": {"company_name": new_name}})
            await db.posts.update_many({"author_id": user["user_id"]}, {"$set": {"author_name": new_name}})
            await db.comments.update_many({"author_id": user["user_id"]}, {"$set": {"author_name": new_name}})
            await db.messages.update_many({"from_id": user["user_id"]}, {"$set": {"from_name": new_name}})
            await db.messages.update_many({"to_id": user["user_id"]}, {"$set": {"to_name": new_name}})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": set_doc})
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password": 0})
    return updated

# ============ ITERATION 5: PREMIUM CANDIDATES ============
@api.get("/candidates/featured")
async def featured_candidates(limit: int = 12):
    """Random selection of candidates with premium priority, weighted shuffle."""
    import random
    premium = await db.users.find({"role": "candidate", "profile.is_premium": True}, {"_id": 0, "password": 0}).to_list(200)
    regular = await db.users.find({"role": "candidate", "profile.is_premium": {"$ne": True}}, {"_id": 0, "password": 0}).to_list(500)
    # Filter expired premium
    now = datetime.now(timezone.utc)
    valid_premium = []
    for p in premium:
        end = p.get("profile", {}).get("premium_end_date")
        if not end:
            # Premium but no end date: still valid
            valid_premium.append(p)
            continue
        try:
            end_dt = datetime.fromisoformat(end)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt > now:
                valid_premium.append(p)
        except Exception:
            # Bad date format → skip premium status, treat as regular
            continue
    random.shuffle(valid_premium)
    random.shuffle(regular)
    n_prem = min(len(valid_premium), max(1, limit // 2)) if valid_premium else 0
    result = valid_premium[:n_prem]
    remaining = limit - len(result)
    result.extend(regular[:remaining])
    # Mark featured flag for UI
    for p in result:
        p["is_premium"] = bool(p.get("profile", {}).get("is_premium"))
    return result

@api.post("/admin/grant-premium/{user_id}")
async def grant_premium(user_id: str, days: int = 30, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin")
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(404, "Introuvable")
    p = target.get("profile", {})
    now = datetime.now(timezone.utc)
    p["is_premium"] = True
    p["premium_start_date"] = now.isoformat()
    p["premium_end_date"] = (now + timedelta(days=days)).isoformat()
    p["premium_status"] = "active"
    await db.users.update_one({"user_id": user_id}, {"$set": {"profile": p}})
    return {"ok": True, "until": p["premium_end_date"]}

# ============ ITERATION 5: MONGO INDEXES ============
async def ensure_indexes():
    try:
        await db.offers.create_index([("city", 1)])
        await db.offers.create_index([("region", 1)])
        await db.offers.create_index([("source", 1)])
        await db.offers.create_index([("status", 1)])
        await db.offers.create_index([("contract_type", 1)])
        await db.offers.create_index([("created_at", -1)])
        await db.offers.create_index([("company_id", 1)])
        await db.users.create_index([("role", 1)])
        await db.users.create_index([("profile.region", 1)])
        await db.users.create_index([("profile.city", 1)])
        await db.users.create_index([("profile.is_premium", 1)])
        await db.applications.create_index([("candidate_id", 1)])
        await db.applications.create_index([("company_id", 1)])
        await db.applications.create_index([("status", 1)])
        await db.messages.create_index([("conv_id", 1), ("created_at", 1)])
        await db.messages.create_index([("to_id", 1), ("read", 1)])
        await db.deals.create_index([("status", 1)])
        await db.deals.create_index([("author_id", 1)])
        await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        await db.profile_views.create_index([("viewed_user_id", 1), ("viewed_at", -1)])
        await db.profile_views.create_index([("viewer_user_id", 1), ("viewed_user_id", 1), ("viewed_at", -1)])
        await db.platform_stats_settings.create_index([("key", 1)], unique=True)
        # TTL index for ad tracking dedup (expires_at field, 0 = use document's own field)
        await db.ad_tracking_dedup.create_index("expires_at", expireAfterSeconds=0)
        # Index for link-preview cache lookups
        await db.link_preview_cache.create_index("url", unique=True)
        # Ads indexes
        await db.ads.create_index([("status", 1)])
        await db.ads.create_index([("company_id", 1)])
        logger.info("Mongo indexes ensured")
    except Exception as e:
        logger.warning(f"Index creation failed: {e}")

# ============ ITERATION 5: REAL FRANCE TRAVAIL CONNECTOR ============
FT_CLIENT_ID = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID")
FT_CLIENT_SECRET = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET")
FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
_ft_token_cache = {"token": None, "expires_at": None}

async def get_france_travail_token():
    now = datetime.now(timezone.utc)
    if _ft_token_cache["token"] and _ft_token_cache["expires_at"] > now:
        return _ft_token_cache["token"]
    if not FT_CLIENT_ID or not FT_CLIENT_SECRET:
        raise HTTPException(503, "France Travail non configuré (FRANCE_TRAVAIL_CLIENT_ID/SECRET requis)")
    r = requests.post(FT_TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": FT_CLIENT_ID, "client_secret": FT_CLIENT_SECRET,
        "scope": "api_offresdemploiv2 o2dsoffre",
    }, timeout=15)
    r.raise_for_status()
    data = r.json()
    _ft_token_cache["token"] = data["access_token"]
    _ft_token_cache["expires_at"] = now + timedelta(seconds=data.get("expires_in", 1500) - 30)
    return _ft_token_cache["token"]

class FranceTravailRealConnector(ExternalConnector):
    name = "FranceTravail"
    enabled = bool(FT_CLIENT_ID and FT_CLIENT_SECRET)
    api_endpoint = "https://candidat.francetravail.fr"

    async def fetch(self, query="", location="", limit=20):
        if not self.enabled:
            # Fall back to simulation
            return [self._make_offer(i, f"Alternance {query or 'Commerce'}", location or "Lyon", "Auvergne-Rhône-Alpes", "alternance") for i in range(limit)]
        token = await get_france_travail_token()
        params = {"natureContrat": "E2,FS", "range": f"0-{min(limit-1, 149)}"}
        if query: params["motsCles"] = query
        if location: params["commune"] = location
        r = requests.get(FT_SEARCH_URL, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
        if r.status_code not in (200, 206):
            logger.error(f"FT API error: {r.status_code} {r.text[:200]}")
            return []
        data = r.json()
        offers = []
        for o in data.get("resultats", []):
            offers.append({
                "offer_id": f"ext_ft_{o.get('id')}",
                "company_id": None,
                "company_name": (o.get("entreprise") or {}).get("nom") or "Entreprise non renseignée",
                "company_logo": (o.get("entreprise") or {}).get("logo"),
                "verified": False, "source": "FranceTravail",
                "external_url": f"https://candidat.francetravail.fr/offres/recherche/detail/{o.get('id')}",
                "title": o.get("intitule", ""),
                "contract_type": "alternance" if (o.get("natureContrat") or "").startswith("Contrat d'apprentissage") or (o.get("typeContrat") or "") == "CAP" else "stage",
                "domain": (o.get("secteurActiviteLibelle") or "Multi-domaine"),
                "city": (o.get("lieuTravail") or {}).get("libelle", "").split(" - ")[-1] if (o.get("lieuTravail") or {}).get("libelle") else "France",
                "region": "France",
                "remote": False, "duration": (o.get("dureeTravailLibelle") or ""),
                "rhythm": None, "start_date": o.get("dateActualisation", ""),
                "level": (o.get("formations") or [{}])[0].get("niveauLibelle", "Tous niveaux"),
                "skills": [c.get("libelle", "") for c in (o.get("competences") or [])[:5]],
                "description": (o.get("description") or "")[:500],
                "profile": "", "benefits": "", "salary": (o.get("salaire") or {}).get("libelle", ""),
                "views": 0, "status": "active",
                "created_at": o.get("dateCreation", datetime.now(timezone.utc).isoformat()),
            })
        return offers

# Replace the stub with the real connector
CONNECTORS["FranceTravail"] = FranceTravailRealConnector()



# ============ ITERATION 6: CV EN LIGNE + PDF EXPORT + AI ============
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors as rl_colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_LEFT

DEFAULT_CV = {
    "professional_title": "",
    "summary": "",
    "availability_date": "",
    "search_status": "en_recherche",
    "contract_type_searched": "stage",
    "mobility": "",
    "phone_visible": True,
    "email_visible": True,
    "visibility": "connected",  # public, connected, after_application, private
    "pdf_template": "modern",  # default template for PDF export (modern, classique, etudiant, alternance, professionnel)
    "educations": [],
    "experiences": [],
    "skills": [],
    "languages": [],
    "projects": [],
    "certifications": [],
    "updated_at": None,
}

@api.get("/cv")
async def get_my_cv(user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    cv = await db.student_cvs.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not cv:
        cv = {"user_id": user["user_id"], **DEFAULT_CV}
        await db.student_cvs.insert_one(cv)
        cv.pop("_id", None)
    return cv

@api.put("/cv")
async def update_my_cv(data: dict, user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    allowed_fields = set(DEFAULT_CV.keys())
    safe = {k: v for k, v in data.items() if k in allowed_fields}
    safe["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.student_cvs.update_one(
        {"user_id": user["user_id"]},
        {"$set": safe, "$setOnInsert": {"user_id": user["user_id"]}},
        upsert=True,
    )
    cv = await db.student_cvs.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return cv

def can_view_cv(cv: dict, viewer: Optional[dict], owner_id: str) -> bool:
    if viewer and viewer["user_id"] == owner_id:
        return True
    visibility = cv.get("visibility", "connected")
    if visibility == "public":
        return True
    if visibility == "private":
        return False
    if not viewer:
        return False
    return True  # connected/after_application: simpler check at API caller side

@api.get("/users/{user_id}/cv")
async def get_user_cv(user_id: str, requester=Depends(get_optional_user)):
    cv = await db.student_cvs.find_one({"user_id": user_id}, {"_id": 0})
    if not cv:
        raise HTTPException(404, "Pas de CV en ligne")
    visibility = cv.get("visibility", "connected")
    is_owner = requester and requester["user_id"] == user_id
    if is_owner:
        return cv
    if visibility == "public":
        return cv
    if visibility == "private":
        raise HTTPException(403, "CV privé")
    if not requester:
        raise HTTPException(401, "Authentification requise")
    if visibility == "connected":
        ct = await db.contacts.find_one({"$or": [
            {"user_a": user_id, "user_b": requester["user_id"]},
            {"user_a": requester["user_id"], "user_b": user_id},
        ]})
        if not ct:
            raise HTTPException(403, "CV réservé aux contacts")
    elif visibility == "after_application":
        ap = await db.applications.find_one({"candidate_id": user_id, "company_id": requester["user_id"]})
        if not ap:
            raise HTTPException(403, "CV accessible après candidature")
    return cv

# ============ PDF EXPORT ============
def _cv_color_palette(template: str):
    """Returns (accent, secondary, text, muted) HexColors for the given template."""
    palettes = {
        "modern":        ("#2563EB", "#DBEAFE", "#0F172A", "#64748B"),
        "classique":     ("#0F172A", "#E2E8F0", "#111827", "#475569"),
        "etudiant":      ("#10B981", "#D1FAE5", "#064E3B", "#475569"),
        "alternance":    ("#8B5CF6", "#EDE9FE", "#1E1B4B", "#6B7280"),
        "professionnel": ("#1E40AF", "#1E293B", "#FFFFFF", "#94A3B8"),
    }
    accent, secondary, text, muted = palettes.get(template, palettes["modern"])
    return rl_colors.HexColor(accent), rl_colors.HexColor(secondary), rl_colors.HexColor(text), rl_colors.HexColor(muted)


def _norm_skills(skills):
    """Skills may be stored as strings or {name,level} dicts; always return a flat list of strings."""
    out = []
    for s in (skills or []):
        if isinstance(s, str):
            if s.strip(): out.append(s.strip())
        elif isinstance(s, dict):
            v = s.get("name") or s.get("label") or s.get("value")
            if v: out.append(str(v))
        else:
            out.append(str(s))
    return out


def _hex(c):
    """ReportLab HexColor → '#rrggbb' for inline HTML."""
    return "#" + c.hexval()[2:]


def _build_sidebar_blocks(cv: dict, body, item_sub, accent, secondary, dark_bg=False):
    """Build right-sidebar content for two-column templates."""
    blocks = []
    sec_title = ParagraphStyle("sbTitle", fontSize=11, fontName="Helvetica-Bold",
                               textColor=accent, spaceBefore=10, spaceAfter=4, leading=14)
    if dark_bg:
        sec_title.textColor = rl_colors.white
        body = ParagraphStyle("sbBody", parent=body, textColor=rl_colors.HexColor("#E2E8F0"))
        item_sub = ParagraphStyle("sbSub", parent=item_sub, textColor=rl_colors.HexColor("#CBD5E1"))

    if cv.get("skills"):
        blocks.append(Paragraph("COMPÉTENCES", sec_title))
        for s in _norm_skills(cv["skills"]):
            blocks.append(Paragraph(f"• {s}", body))
    if cv.get("languages"):
        blocks.append(Paragraph("LANGUES", sec_title))
        for lang in cv["languages"]:
            blocks.append(Paragraph(f"• {lang.get('language','')} — {lang.get('level','')}", body))
    if cv.get("certifications"):
        blocks.append(Paragraph("CERTIFICATIONS", sec_title))
        for c in cv["certifications"]:
            blocks.append(Paragraph(c.get("name",""), body))
            if c.get("issuer") or c.get("date"):
                blocks.append(Paragraph(f"{c.get('issuer','')} · {c.get('date','')}", item_sub))
    return blocks


def build_cv_pdf(user: dict, cv: dict, template: str = "modern") -> bytes:
    template = template if template in {"modern", "classique", "etudiant", "alternance", "professionnel"} else "modern"
    buf = io.BytesIO()
    accent, secondary, text_color, muted = _cv_color_palette(template)
    p = user.get("profile", {})

    contact_bits = []
    if cv.get("email_visible", True): contact_bits.append(user.get("email", ""))
    if cv.get("phone_visible", True) and p.get("mobile"): contact_bits.append(p["mobile"])
    if p.get("city"): contact_bits.append(p["city"])
    if cv.get("mobility"): contact_bits.append(f"Mobilité: {cv['mobility']}")

    # --- Build common styles ---
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14,
                          spaceAfter=6, textColor=text_color)
    item_title = ParagraphStyle("itemTitle", parent=styles["Normal"], fontSize=11,
                                fontName="Helvetica-Bold", spaceAfter=1, textColor=text_color)
    item_sub = ParagraphStyle("itemSub", parent=styles["Normal"], fontSize=9,
                              textColor=muted, spaceAfter=4)

    elements = []

    # ===== TEMPLATE: CLASSIQUE — serif, centered name, sober =====
    if template == "classique":
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2.2*cm, rightMargin=2.2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        name_style = ParagraphStyle("name", parent=styles["Title"], fontName="Times-Bold",
                                    fontSize=24, alignment=1, textColor=text_color, spaceAfter=2)
        sub = ParagraphStyle("sub", parent=styles["Normal"], fontName="Times-Italic",
                             fontSize=12, alignment=1, textColor=muted, spaceAfter=8)
        section_style = ParagraphStyle("section", parent=styles["Heading2"], fontName="Times-Bold",
                                       fontSize=12, textColor=text_color, alignment=0,
                                       borderPadding=4, spaceBefore=14, spaceAfter=6)
        body = ParagraphStyle("body", parent=body, fontName="Times-Roman")
        item_title = ParagraphStyle("itemTitle", parent=item_title, fontName="Times-Bold")
        elements.append(Paragraph(user.get("name", ""), name_style))
        if cv.get("professional_title"):
            elements.append(Paragraph(cv["professional_title"], sub))
        if contact_bits:
            elements.append(Paragraph(" · ".join(contact_bits), ParagraphStyle("ctc", parent=item_sub, alignment=1)))
        # Decorative divider
        from reportlab.platypus import HRFlowable
        elements.append(HRFlowable(width="60%", thickness=0.7, lineCap="round",
                                   color=accent, spaceBefore=4, spaceAfter=8, hAlign="CENTER"))
        sections = [
            ("Profil", lambda: [Paragraph(cv["summary"], body)] if cv.get("summary") else []),
            ("Expériences", lambda: _exp_block(cv, item_title, item_sub, body)),
            ("Formation", lambda: _edu_block(cv, item_title, item_sub, body)),
            ("Compétences", lambda: [Paragraph(" · ".join(_norm_skills(cv["skills"])), body)] if cv.get("skills") else []),
            ("Langues", lambda: _lang_block(cv, body)),
            ("Projets", lambda: _proj_block(cv, item_title, item_sub, body)),
            ("Certifications", lambda: _cert_block(cv, item_title, item_sub)),
        ]
        for title_, fn in sections:
            blocks = fn()
            if blocks:
                elements.append(Paragraph(title_.upper(), section_style))
                elements.extend(blocks)
        doc.build(elements)
        return buf.getvalue()

    # ===== TEMPLATE: ETUDIANT — friendly, larger color blocks =====
    if template == "etudiant":
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm,
                                topMargin=1.5*cm, bottomMargin=1.8*cm)
        # Coloured banner table with name
        from reportlab.platypus import Table, TableStyle
        banner_inner = [
            Paragraph(f'<font color="white" size="22"><b>{user.get("name","")}</b></font>', styles["Normal"]),
            Paragraph(f'<font color="white" size="12">{cv.get("professional_title","")}</font>', styles["Normal"]),
            Paragraph(f'<font color="#E0F2FE" size="9">{" · ".join(contact_bits)}</font>', styles["Normal"]),
        ]
        banner = Table([[banner_inner]], colWidths=[doc.width])
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), accent),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 14),
            ("BOTTOMPADDING", (0,0), (-1,-1), 14),
            ("ROUNDEDCORNERS", [10,10,10,10]),
        ]))
        elements.append(banner)
        elements.append(Spacer(1, 12))
        section_style = ParagraphStyle("section", parent=styles["Heading2"], fontSize=13,
                                       fontName="Helvetica-Bold", textColor=accent,
                                       spaceBefore=14, spaceAfter=4)
        if cv.get("summary"):
            elements.append(Paragraph("À propos de moi", section_style))
            elements.append(Paragraph(cv["summary"], body))
        if cv.get("educations"):
            elements.append(Paragraph("🎓 Formation", section_style))
            elements.extend(_edu_block(cv, item_title, item_sub, body))
        if cv.get("experiences"):
            elements.append(Paragraph("💼 Expériences", section_style))
            elements.extend(_exp_block(cv, item_title, item_sub, body))
        if cv.get("skills"):
            elements.append(Paragraph("⚡ Compétences", section_style))
            # Skill chips as Paragraphs
            chips = " ".join([f'<font color="white" backColor="{_hex(accent)}"> {s} </font>' for s in _norm_skills(cv["skills"])])
            elements.append(Paragraph(chips, body))
        if cv.get("languages"):
            elements.append(Paragraph("🌐 Langues", section_style))
            elements.extend(_lang_block(cv, body))
        if cv.get("projects"):
            elements.append(Paragraph("🚀 Projets", section_style))
            elements.extend(_proj_block(cv, item_title, item_sub, body))
        if cv.get("certifications"):
            elements.append(Paragraph("🏆 Certifications", section_style))
            elements.extend(_cert_block(cv, item_title, item_sub))
        doc.build(elements)
        return buf.getvalue()

    # ===== TEMPLATE: ALTERNANCE — two-column, violet, formation + experience focused =====
    if template == "alternance":
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        name_style = ParagraphStyle("name", parent=styles["Title"], fontSize=20,
                                    textColor=accent, spaceAfter=2)
        title_style = ParagraphStyle("title", parent=styles["Normal"], fontSize=12,
                                     textColor=muted, spaceAfter=8)
        section_style = ParagraphStyle("section", parent=styles["Heading2"], fontSize=11,
                                       fontName="Helvetica-Bold", textColor=accent,
                                       spaceBefore=10, spaceAfter=4)
        # Header banner
        elements.append(Paragraph(user.get("name", ""), name_style))
        if cv.get("professional_title"):
            elements.append(Paragraph(cv["professional_title"] + "  ·  <b>Recherche alternance</b>", title_style))
        if contact_bits:
            elements.append(Paragraph(" · ".join(contact_bits), item_sub))
        from reportlab.platypus import HRFlowable
        elements.append(HRFlowable(width="100%", thickness=1.5, color=accent, spaceBefore=6, spaceAfter=8))
        if cv.get("summary"):
            elements.append(Paragraph("PROJET PROFESSIONNEL", section_style))
            elements.append(Paragraph(cv["summary"], body))

        # 2-column: Left (Experiences + Projects), Right (Formation + Skills + Languages + Certifications)
        left = []
        if cv.get("experiences"):
            left.append(Paragraph("EXPÉRIENCES & STAGES", section_style))
            left.extend(_exp_block(cv, item_title, item_sub, body))
        if cv.get("projects"):
            left.append(Paragraph("PROJETS", section_style))
            left.extend(_proj_block(cv, item_title, item_sub, body))
        right = []
        if cv.get("educations"):
            right.append(Paragraph("FORMATION", section_style))
            right.extend(_edu_block(cv, item_title, item_sub, body))
        right.extend(_build_sidebar_blocks(cv, body, item_sub, accent, secondary))
        from reportlab.platypus import Table, TableStyle
        col_w = (doc.width - 0.5*cm) / 2
        cols = Table([[left, right]], colWidths=[col_w, col_w])
        cols.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ]))
        elements.append(cols)
        doc.build(elements)
        return buf.getvalue()

    # ===== TEMPLATE: PROFESSIONNEL — dark sidebar, formal =====
    if template == "professionnel":
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=0*cm, rightMargin=0*cm,
                                topMargin=0*cm, bottomMargin=0*cm)
        # build main + sidebar columns
        sb_title_color = rl_colors.white
        main_body = ParagraphStyle("mainBody", fontSize=10, leading=14, spaceAfter=6,
                                   textColor=rl_colors.HexColor("#0F172A"))
        main_section = ParagraphStyle("mainSection", fontSize=11, fontName="Helvetica-Bold",
                                      textColor=accent, spaceBefore=12, spaceAfter=4)
        main_item_title = ParagraphStyle("mit", fontSize=11, fontName="Helvetica-Bold",
                                         textColor=rl_colors.HexColor("#0F172A"), spaceAfter=1)
        main_item_sub = ParagraphStyle("mis", fontSize=9, textColor=rl_colors.HexColor("#475569"), spaceAfter=4)
        main_col = []
        main_col.append(Paragraph(f'<font size="22" color="{_hex(accent)}"><b>{user.get("name","")}</b></font>', main_body))
        if cv.get("professional_title"):
            main_col.append(Paragraph(f'<font size="13" color="#475569">{cv["professional_title"]}</font>', main_body))
        main_col.append(Spacer(1, 8))
        if cv.get("summary"):
            main_col.append(Paragraph("PROFIL", main_section))
            main_col.append(Paragraph(cv["summary"], main_body))
        if cv.get("experiences"):
            main_col.append(Paragraph("EXPÉRIENCE PROFESSIONNELLE", main_section))
            main_col.extend(_exp_block(cv, main_item_title, main_item_sub, main_body))
        if cv.get("educations"):
            main_col.append(Paragraph("FORMATION", main_section))
            main_col.extend(_edu_block(cv, main_item_title, main_item_sub, main_body))
        if cv.get("projects"):
            main_col.append(Paragraph("PROJETS", main_section))
            main_col.extend(_proj_block(cv, main_item_title, main_item_sub, main_body))

        sb_body = ParagraphStyle("sbBody", fontSize=10, leading=14, spaceAfter=4,
                                 textColor=rl_colors.HexColor("#E2E8F0"))
        sb_section = ParagraphStyle("sbSec", fontSize=11, fontName="Helvetica-Bold",
                                    textColor=rl_colors.white, spaceBefore=12, spaceAfter=4)
        sb_sub = ParagraphStyle("sbSub", fontSize=9, textColor=rl_colors.HexColor("#94A3B8"), spaceAfter=4)
        sidebar = []
        sidebar.append(Paragraph("CONTACT", sb_section))
        for b in contact_bits:
            sidebar.append(Paragraph(b, sb_body))
        if cv.get("skills"):
            sidebar.append(Paragraph("COMPÉTENCES", sb_section))
            for s in _norm_skills(cv["skills"]):
                sidebar.append(Paragraph(f"• {s}", sb_body))
        if cv.get("languages"):
            sidebar.append(Paragraph("LANGUES", sb_section))
            for lang in cv["languages"]:
                sidebar.append(Paragraph(f"• {lang.get('language','')} — {lang.get('level','')}", sb_body))
        if cv.get("certifications"):
            sidebar.append(Paragraph("CERTIFICATIONS", sb_section))
            for c in cv["certifications"]:
                sidebar.append(Paragraph(c.get("name",""), sb_body))
                if c.get("issuer") or c.get("date"):
                    sidebar.append(Paragraph(f"{c.get('issuer','')} · {c.get('date','')}", sb_sub))
        from reportlab.platypus import Table, TableStyle
        page_w = A4[0]
        sb_w = 6.2*cm
        main_w = page_w - sb_w
        layout = Table([[main_col, sidebar]], colWidths=[main_w, sb_w])
        layout.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("BACKGROUND", (1,0), (1,-1), rl_colors.HexColor("#1E293B")),
            ("LEFTPADDING", (0,0), (0,0), 24),
            ("RIGHTPADDING", (0,0), (0,0), 18),
            ("TOPPADDING", (0,0), (0,0), 26),
            ("BOTTOMPADDING", (0,0), (0,0), 26),
            ("LEFTPADDING", (1,0), (1,0), 16),
            ("RIGHTPADDING", (1,0), (1,0), 16),
            ("TOPPADDING", (1,0), (1,0), 26),
            ("BOTTOMPADDING", (1,0), (1,0), 26),
        ]))
        # Force full page height for sidebar background
        elements.append(layout)
        doc.build(elements)
        return buf.getvalue()

    # ===== TEMPLATE: MODERN (default) — clean single column, blue accent =====
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    name_style = ParagraphStyle("name", parent=styles["Title"], fontSize=22,
                                textColor=accent, alignment=TA_LEFT, spaceAfter=4)
    title_style = ParagraphStyle("title", parent=styles["Normal"], fontSize=13,
                                 textColor=muted, spaceAfter=12)
    section_style = ParagraphStyle("section", parent=styles["Heading2"], fontSize=12,
                                   textColor=accent, spaceBefore=14, spaceAfter=4)
    elements.append(Paragraph(user.get("name", ""), name_style))
    if cv.get("professional_title"):
        elements.append(Paragraph(cv["professional_title"], title_style))
    if contact_bits:
        elements.append(Paragraph(" · ".join(contact_bits), item_sub))
    if cv.get("summary"):
        elements.append(Paragraph("Profil", section_style))
        elements.append(Paragraph(cv["summary"], body))
    if cv.get("experiences"):
        elements.append(Paragraph("Expériences professionnelles", section_style))
        elements.extend(_exp_block(cv, item_title, item_sub, body))
    if cv.get("educations"):
        elements.append(Paragraph("Formation", section_style))
        elements.extend(_edu_block(cv, item_title, item_sub, body))
    if cv.get("skills"):
        elements.append(Paragraph("Compétences", section_style))
        elements.append(Paragraph(" · ".join(_norm_skills(cv["skills"])), body))
    if cv.get("languages"):
        elements.append(Paragraph("Langues", section_style))
        elements.extend(_lang_block(cv, body))
    if cv.get("projects"):
        elements.append(Paragraph("Projets", section_style))
        elements.extend(_proj_block(cv, item_title, item_sub, body))
    if cv.get("certifications"):
        elements.append(Paragraph("Certifications", section_style))
        elements.extend(_cert_block(cv, item_title, item_sub))
    doc.build(elements)
    return buf.getvalue()


def _exp_block(cv, item_title, item_sub, body):
    out = []
    for e in cv.get("experiences", []):
        out.append(Paragraph(f"{e.get('job_title','')} — {e.get('company_name','')}", item_title))
        sub = " · ".join(filter(None, [e.get("city",""),
                                       f"{e.get('start_date','')} → {e.get('end_date','') or 'En cours'}",
                                       e.get("experience_type","")]))
        if sub: out.append(Paragraph(sub, item_sub))
        if e.get("description"): out.append(Paragraph(e["description"], body))
    return out

def _edu_block(cv, item_title, item_sub, body):
    out = []
    for ed in cv.get("educations", []):
        out.append(Paragraph(f"{ed.get('degree','')} — {ed.get('school','')}", item_title))
        sub = " · ".join(filter(None, [ed.get("city",""),
                                       f"{ed.get('start_date','')} → {ed.get('end_date','')}",
                                       ed.get("level","")]))
        if sub: out.append(Paragraph(sub, item_sub))
        if ed.get("description"): out.append(Paragraph(ed["description"], body))
    return out

def _lang_block(cv, body):
    return [Paragraph(f"{l.get('language','')} — {l.get('level','')}", body)
            for l in cv.get("languages", [])]

def _proj_block(cv, item_title, item_sub, body):
    out = []
    for pr in cv.get("projects", []):
        out.append(Paragraph(pr.get("name",""), item_title))
        if pr.get("description"): out.append(Paragraph(pr["description"], body))
        if pr.get("link"): out.append(Paragraph(pr["link"], item_sub))
    return out

def _cert_block(cv, item_title, item_sub):
    out = []
    for c in cv.get("certifications", []):
        out.append(Paragraph(f"{c.get('name','')} — {c.get('issuer','')}", item_title))
        if c.get("date"): out.append(Paragraph(c["date"], item_sub))
    return out

@api.get("/cv/export")
async def export_my_cv(template: str = "modern", user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    cv = await db.student_cvs.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not cv:
        raise HTTPException(404, "Pas de CV à exporter")
    pdf_bytes = build_cv_pdf(user, cv, template)
    # Log export
    await db.cv_exports.insert_one({
        "export_id": f"cve_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"], "template": template,
        "size": len(pdf_bytes),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return FResponse(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f'inline; filename="CV-{user["name"].replace(" ","_")}.pdf"'})

@api.get("/users/{user_id}/cv/export")
async def export_user_cv(user_id: str, template: str = "modern", requester=Depends(get_current_user)):
    cv = await db.student_cvs.find_one({"user_id": user_id}, {"_id": 0})
    if not cv:
        raise HTTPException(404, "Pas de CV en ligne")
    visibility = cv.get("visibility", "connected")
    if visibility == "public" or requester["user_id"] == user_id or requester["role"] == "admin":
        pass
    elif visibility == "connected":
        ct = await db.contacts.find_one({"$or": [
            {"user_a": user_id, "user_b": requester["user_id"]},
            {"user_a": requester["user_id"], "user_b": user_id},
        ]})
        if not ct: raise HTTPException(403, "Réservé aux contacts")
    elif visibility == "after_application":
        ap = await db.applications.find_one({"candidate_id": user_id, "company_id": requester["user_id"]})
        if not ap: raise HTTPException(403, "Accessible après candidature")
    else:
        raise HTTPException(403, "CV privé")
    owner = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password": 0})
    pdf_bytes = build_cv_pdf(owner, cv, template)
    return FResponse(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f'attachment; filename="CV-{owner["name"].replace(" ","_")}.pdf"'})


@api.get("/applications/{app_id}/cv")
async def get_application_cv(app_id: str, user=Depends(get_current_user)):
    """Returns the snapshot of the online CV attached to an application (company + candidate access)."""
    a = await db.applications.find_one({"app_id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Candidature introuvable")
    if user["user_id"] not in (a["candidate_id"], a["company_id"]) and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    if not a.get("use_online_cv") or not a.get("online_cv_snapshot"):
        raise HTTPException(404, "Pas de CV en ligne joint à cette candidature")
    candidate = await db.users.find_one({"user_id": a["candidate_id"]}, {"_id": 0, "password": 0})
    return {
        "cv": a["online_cv_snapshot"],
        "candidate": candidate,
        "template": a.get("online_cv_template", "modern"),
    }


@api.get("/applications/{app_id}/cv/export")
async def export_application_cv(app_id: str, template: Optional[str] = None, user=Depends(get_current_user)):
    """Exports the snapshot CV attached to an application as a PDF."""
    a = await db.applications.find_one({"app_id": app_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Candidature introuvable")
    if user["user_id"] not in (a["candidate_id"], a["company_id"]) and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    if not a.get("use_online_cv") or not a.get("online_cv_snapshot"):
        raise HTTPException(404, "Pas de CV en ligne joint à cette candidature")
    owner = await db.users.find_one({"user_id": a["candidate_id"]}, {"_id": 0, "password": 0})
    tpl = template or a.get("online_cv_template") or "modern"
    pdf_bytes = build_cv_pdf(owner, a["online_cv_snapshot"], tpl)
    return FResponse(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f'attachment; filename="CV-{owner["name"].replace(" ","_")}.pdf"'})

# ============ AI ASSISTANT ============
from emergentintegrations.llm.chat import LlmChat, UserMessage

async def call_ai(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(503, "Service IA indisponible (clé manquante)")
    session_id = f"cv_{uuid.uuid4().hex[:8]}"
    chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_prompt).with_model("openai", model)
    msg = UserMessage(text=user_prompt)
    return await chat.send_message(msg)

@api.post("/cv/ai/{action}")
async def cv_ai(action: str, body: dict, user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    text = body.get("text", "").strip()
    context = body.get("context", "")
    if action == "improve":
        sys = "Tu es un coach carrière. Améliore le texte fourni en restant fidèle au fond mais en le rendant plus impactant, structuré et professionnel. Réponds UNIQUEMENT avec le texte amélioré, sans préambule."
        prompt = text
    elif action == "rephrase":
        sys = "Reformule le texte fourni de manière plus claire et professionnelle. Réponds UNIQUEMENT avec la reformulation."
        prompt = text
    elif action == "correct":
        sys = "Corrige les fautes d'orthographe et de grammaire du texte. Garde le sens identique. Réponds UNIQUEMENT avec le texte corrigé."
        prompt = text
    elif action == "summary":
        sys = "Génère un résumé professionnel de 3-4 phrases pour un CV étudiant, basé sur les infos fournies. Ton positif, dynamique. Réponds UNIQUEMENT avec le résumé."
        prompt = f"Profil: {text}\nContexte: {context}"
    elif action == "skills":
        sys = "Propose 8 à 12 compétences professionnelles pertinentes pour le profil décrit. Réponds UNIQUEMENT avec une liste séparée par des virgules, sans numérotation."
        prompt = f"Profil: {text}\nDomaine: {context}"
    elif action == "cover_letter":
        sys = "Tu rédiges une lettre de motivation professionnelle en français pour un étudiant français cherchant un stage ou une alternance. Ton: respectueux, motivé, concis (250 mots max)."
        prompt = f"Profil du candidat: {text}\nOffre / entreprise visée: {context}"
    elif action == "adapt":
        sys = "Adapte le texte du CV à l'offre fournie en mettant en avant les compétences pertinentes. Réponds UNIQUEMENT avec le texte adapté."
        prompt = f"Texte original: {text}\nOffre visée: {context}"
    else:
        raise HTTPException(400, f"Action IA inconnue: {action}")
    try:
        result = await call_ai(sys, prompt)
    except Exception as e:
        logger.error(f"AI error: {e}")
        raise HTTPException(500, "Erreur IA. Réessayez.")
    return {"suggestion": result}


# ============ ITERATION 7: THEME PREFERENCE + PROFILE VIEWS + PLATFORM STATS ============

@api.patch("/me/theme")
async def update_my_theme(body: dict, user=Depends(get_current_user)):
    pref = body.get("theme_preference")
    if pref not in ("light", "dark", "system"):
        raise HTTPException(400, "Valeur invalide (light, dark, system)")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"theme_preference": pref}})
    return {"ok": True, "theme_preference": pref}


def _is_premium(user: dict) -> bool:
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    p = user.get("profile") or {}
    is_p = user.get("is_premium") or p.get("is_premium")
    if not is_p:
        return False
    end = user.get("premium_end_date") or p.get("premium_end_date")
    if not end:
        return True
    try:
        return datetime.fromisoformat(str(end).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception:
        return bool(is_p)


@api.get("/me/profile-views/stats")
async def my_profile_view_stats(user=Depends(get_current_user)):
    """Aggregated view counts for the current user (Free + Premium see this)."""
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()
    total = await db.profile_views.count_documents({"viewed_user_id": user["user_id"]})
    week = await db.profile_views.count_documents({"viewed_user_id": user["user_id"], "viewed_at": {"$gte": week_ago}})
    month = await db.profile_views.count_documents({"viewed_user_id": user["user_id"], "viewed_at": {"$gte": month_ago}})
    # Count distinct viewers
    distinct = await db.profile_views.distinct("viewer_user_id", {"viewed_user_id": user["user_id"]})
    return {
        "total": total,
        "week": week,
        "month": month,
        "distinct_viewers": len(distinct),
        "is_premium": _is_premium(user),
    }


@api.get("/me/profile-views")
async def my_profile_views_list(limit: int = 30, user=Depends(get_current_user)):
    """Detail list — Premium only (per user choice b: free=nothing, premium=all)."""
    if not _is_premium(user):
        raise HTTPException(402, "Réservé aux profils Premium")
    docs = await db.profile_views.find(
        {"viewed_user_id": user["user_id"]}, {"_id": 0}
    ).sort("viewed_at", -1).limit(limit).to_list(limit)
    # Enrich with current viewer info (in case avatar/name changed)
    out = []
    for d in docs:
        v = await db.users.find_one({"user_id": d.get("viewer_user_id")}, {"_id": 0, "password": 0, "email": 0})
        out.append({
            "view_id": d.get("view_id"),
            "viewer_user_id": d.get("viewer_user_id"),
            "viewer_name": v.get("name") if v else d.get("viewer_name"),
            "viewer_role": v.get("role") if v else d.get("viewer_role"),
            "viewer_avatar": (v.get("profile", {}).get("avatar") or v.get("profile", {}).get("logo")) if v else d.get("viewer_avatar"),
            "viewer_title": (v.get("profile", {}).get("title") or v.get("profile", {}).get("sector")) if v else None,
            "viewed_at": d.get("viewed_at"),
        })
    return out


# ===== Platform-wide social proof =====
OBTAINED_STATUSES = {"acceptee", "internship_obtained", "apprenticeship_obtained", "contract_signed"}


@api.get("/stats/platform")
async def platform_stats():
    """Public counter used for social proof on landing + dashboards."""
    settings = await db.platform_stats_settings.find_one({"key": "main"}, {"_id": 0}) or {}
    real_count = await db.applications.count_documents({"status": {"$in": list(OBTAINED_STATUSES)}})
    use_manual = settings.get("use_manual_count", False)
    displayed = settings.get("displayed_obtained_count", 0) if use_manual else real_count
    return {
        "real_obtained_count": real_count,
        "displayed_obtained_count": displayed,
        "use_manual_count": bool(use_manual),
        "public_message": settings.get("public_message") or "étudiants ont trouvé un stage ou une alternance via StageEtudiant",
        "show_counter": settings.get("show_counter", True),
        "total_companies": await db.users.count_documents({"role": "company"}),
        "total_candidates": await db.users.count_documents({"role": "candidate"}),
        "total_offers": await db.offers.count_documents({}),
    }


@api.get("/admin/platform-stats")
async def admin_platform_stats(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Réservé aux admins")
    settings = await db.platform_stats_settings.find_one({"key": "main"}, {"_id": 0}) or {
        "key": "main",
        "displayed_obtained_count": 0,
        "use_manual_count": False,
        "public_message": "étudiants ont trouvé un stage ou une alternance via StageEtudiant",
        "show_counter": True,
    }
    real_count = await db.applications.count_documents({"status": {"$in": list(OBTAINED_STATUSES)}})
    return {**settings, "real_obtained_count": real_count}


@api.put("/admin/platform-stats")
async def admin_set_platform_stats(body: dict, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Réservé aux admins")
    update = {
        "displayed_obtained_count": int(body.get("displayed_obtained_count", 0)),
        "use_manual_count": bool(body.get("use_manual_count", False)),
        "public_message": str(body.get("public_message") or "étudiants ont trouvé un stage ou une alternance via StageEtudiant")[:200],
        "show_counter": bool(body.get("show_counter", True)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.platform_stats_settings.update_one(
        {"key": "main"},
        {"$set": update, "$setOnInsert": {"key": "main"}},
        upsert=True,
    )
    return {"ok": True, **update}


app.include_router(api)


# ============ ITERATION 8: Phase B — External Companies (Annuaire / Recherche d'Entreprises gouv.fr) ============
from external_companies import (
    search_companies as ext_search,
    get_company_by_siret as ext_get,
)

ext_api = APIRouter(prefix="/api")

@ext_api.get("/companies/search")
async def companies_search(
    q: Optional[str] = None,
    code_postal: Optional[str] = None,
    departement: Optional[str] = None,
    region: Optional[str] = None,
    activite_principale: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    user=Depends(get_optional_user),  # logged user not required but tracked if present
):
    """Search French companies via the public Annuaire d'Entreprises API (cached 7d)."""
    if not any([q, code_postal, departement, region, activite_principale]):
        raise HTTPException(400, "Au moins un critère de recherche est requis")
    return await ext_search(
        db, q=q, code_postal=code_postal, departement=departement, region=region,
        activite_principale=activite_principale, page=page, per_page=per_page,
    )


@ext_api.get("/companies/siret/{siret}")
async def companies_get_by_siret(siret: str):
    """Fetch company by SIRET (or SIREN). Cached 30 days."""
    data = await ext_get(db, siret)
    if not data:
        raise HTTPException(404, "Entreprise introuvable")
    return data


@ext_api.post("/admin/external-cache/refresh")
async def admin_refresh_external_cache(body: dict, user=Depends(get_current_user)):
    """Admin: force a re-fetch (bypass cache) for a given search or SIRET."""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    kind = body.get("kind", "search")
    if kind == "siret":
        siret = body.get("siret")
        if not siret: raise HTTPException(400, "siret requis")
        return await ext_get(db, siret, force_refresh=True)
    return await ext_search(
        db, q=body.get("q"), code_postal=body.get("code_postal"),
        departement=body.get("departement"), region=body.get("region"),
        activite_principale=body.get("activite_principale"),
        page=int(body.get("page", 1)), per_page=int(body.get("per_page", 10)),
        force_refresh=True,
    )


@ext_api.delete("/admin/external-cache")
async def admin_clear_external_cache(scope: str = "all", user=Depends(get_current_user)):
    """Admin: purge external company cache. scope=search|details|all"""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    deleted = {"search": 0, "details": 0}
    if scope in ("search", "all"):
        r = await db.external_company_search_cache.delete_many({})
        deleted["search"] = r.deleted_count
    if scope in ("details", "all"):
        r = await db.external_company_details_cache.delete_many({})
        deleted["details"] = r.deleted_count
    return {"ok": True, "deleted": deleted}


@ext_api.get("/admin/external-cache")
async def admin_list_external_cache(limit: int = 30, user=Depends(get_current_user)):
    """Admin: list cached entries + recent api logs."""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    searches = await db.external_company_search_cache.find(
        {}, {"_id": 0, "results": 0}
    ).sort("cached_at", -1).limit(limit).to_list(limit)
    details = await db.external_company_details_cache.find(
        {}, {"_id": 0}
    ).sort("cached_at", -1).limit(limit).to_list(limit)
    logs = await db.api_request_logs.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    errors = await db.api_error_logs.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    return {
        "search_cache_count": len(searches),
        "details_cache_count": len(details),
        "search_cache_entries": searches,
        "details_cache_entries": details,
        "recent_logs": logs,
        "recent_errors": errors,
    }


app.include_router(ext_api)  # register Phase B external company endpoints


# ============ ITERATION 9: Phase C — Student company lists + Phase D — AI search + history + Phase E — Admin analytics ============
phase_api = APIRouter(prefix="/api")

# ---------- Phase C: Student personal company lists ----------
TRACK_STATUSES = {
    "a_contacter", "cv_envoye", "relance_a_faire", "relance",
    "reponse_recue", "refus", "entretien_obtenu",
    "stage_obtenu", "alternance_obtenue",
}


@phase_api.post("/me/companies")
async def add_company_to_list(body: dict, user=Depends(get_current_user)):
    """Add an external (or internal) company to the student's tracking list."""
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    siret = body.get("siret")
    siren = body.get("siren")
    name = body.get("name")
    if not name:
        raise HTTPException(400, "Nom requis")
    # idempotent on (user_id, siret) when siret present, else on (user_id, name)
    key = {"user_id": user["user_id"]}
    if siret: key["siret"] = siret
    else: key["name"] = name
    existing = await db.student_company_lists.find_one(key)
    if existing:
        return {"ok": True, "duplicate": True, "id": existing["id"]}
    doc = {
        "id": f"tc_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "name": name,
        "siret": siret,
        "siren": siren,
        "city": body.get("city"),
        "postal_code": body.get("postal_code"),
        "region": body.get("region"),
        "address": body.get("address"),
        "naf_code": body.get("naf_code"),
        "website": body.get("website"),
        "email": body.get("email"),
        "phone": body.get("phone"),
        "status": body.get("status", "a_contacter"),
        "note": body.get("note", ""),
        "relance_date": body.get("relance_date"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.student_company_lists.insert_one(doc)
    doc.pop("_id", None)
    return doc


@phase_api.get("/me/companies")
async def my_company_list(status: Optional[str] = None, user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    q = {"user_id": user["user_id"]}
    if status: q["status"] = status
    items = await db.student_company_lists.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return items


@phase_api.patch("/me/companies/{item_id}")
async def update_company_list_item(item_id: str, body: dict, user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    item = await db.student_company_lists.find_one({"id": item_id, "user_id": user["user_id"]})
    if not item:
        raise HTTPException(404, "Introuvable")
    allowed = {"status", "note", "relance_date", "email", "phone", "website"}
    set_doc = {k: v for k, v in body.items() if k in allowed}
    if "status" in set_doc and set_doc["status"] not in TRACK_STATUSES:
        raise HTTPException(400, f"Statut invalide. Acceptés: {sorted(TRACK_STATUSES)}")
    set_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.student_company_lists.update_one({"id": item_id}, {"$set": set_doc})
    return {"ok": True, **set_doc}


@phase_api.delete("/me/companies/{item_id}")
async def delete_company_list_item(item_id: str, user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    r = await db.student_company_lists.delete_one({"id": item_id, "user_id": user["user_id"]})
    return {"ok": True, "deleted": r.deleted_count}


@phase_api.get("/me/companies/export")
async def export_company_list(fmt: str = "csv", user=Depends(get_current_user)):
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    items = await db.student_company_lists.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    columns = ["name", "siret", "naf_code", "address", "city", "postal_code", "region",
               "website", "email", "phone", "status", "note", "relance_date"]
    headers = ["Nom entreprise", "SIRET", "NAF/APE", "Adresse", "Ville", "Code postal", "Région",
               "Site web", "Email", "Téléphone", "Statut", "Note", "Date relance"]
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        import csv, io as _io
        buf = _io.StringIO()
        w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        w.writerow(headers)
        for it in items: w.writerow([(it.get(c) or "") for c in columns])
        return FResponse(content=buf.getvalue(), media_type="text/csv",
                         headers={"Content-Disposition": 'attachment; filename="entreprises.csv"'})
    if fmt == "xlsx":
        try:
            import openpyxl
        except Exception:
            raise HTTPException(503, "Export XLSX indisponible (openpyxl absent)")
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Entreprises"
        ws.append(headers)
        for it in items: ws.append([(it.get(c) or "") for c in columns])
        buf = io.BytesIO(); wb.save(buf)
        return FResponse(content=buf.getvalue(),
                         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         headers={"Content-Disposition": 'attachment; filename="entreprises.xlsx"'})
    if fmt == "pdf":
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table as RTable, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors as rl_c
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        title = Paragraph(f"Ma liste d'entreprises ({len(items)})", styles["Title"])
        rows = [["Entreprise", "Ville", "NAF", "Statut", "Relance", "Note"]]
        for it in items:
            rows.append([it.get("name",""), it.get("city",""), it.get("naf_code",""),
                         it.get("status",""), it.get("relance_date","") or "", (it.get("note","") or "")[:60]])
        t = RTable(rows, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), rl_c.HexColor("#2563EB")),
            ("TEXTCOLOR", (0,0), (-1,0), rl_c.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.3, rl_c.HexColor("#94A3B8")),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [rl_c.white, rl_c.HexColor("#F1F5F9")]),
        ]))
        doc.build([title, t])
        return FResponse(content=buf.getvalue(), media_type="application/pdf",
                         headers={"Content-Disposition": 'attachment; filename="entreprises.pdf"'})
    raise HTTPException(400, "Format invalide (csv|xlsx|pdf)")


@phase_api.post("/ai/spontaneous-message")
async def ai_spontaneous_message(body: dict, user=Depends(get_current_user)):
    """Generate a spontaneous-application message from candidate profile + target company info."""
    if user["role"] != "candidate":
        raise HTTPException(403, "Étudiants uniquement")
    company = body.get("company") or {}
    candidate_brief = body.get("brief") or ""
    cv = await db.student_cvs.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    profile_summary = f"{cv.get('professional_title','')}. {cv.get('summary','')}. Compétences: {', '.join(cv.get('skills', []))}"
    company_summary = f"{company.get('name','')} ({company.get('city','')}, NAF {company.get('naf_code','')})"
    sys = ("Rédige un message court (<200 mots), poli et impactant, pour une candidature spontanée en stage/alternance. "
           "Personnalise selon l'entreprise visée. Termine par une signature 'Cordialement,'. Réponds UNIQUEMENT avec le message.")
    prompt = f"Profil candidat: {profile_summary}\nProjet: {candidate_brief or cv.get('contract_type_searched','stage')}\nEntreprise visée: {company_summary}"
    try:
        result = await call_ai(sys, prompt)
    except Exception as e:
        logger.error(f"AI spontaneous error: {e}")
        raise HTTPException(500, "Erreur IA")
    return {"message": result}


# ---------- Phase D: AI natural-language search + search history ----------
@phase_api.post("/ai/search")
async def ai_search(body: dict, user=Depends(get_optional_user)):
    """Extract structured search criteria from a natural-language query."""
    text = (body.get("query") or "").strip()
    if not text:
        raise HTTPException(400, "Requête vide")
    sys = ("Tu es un assistant qui transforme une requête en français en critères de recherche JSON. "
           "Retourne UNIQUEMENT un JSON valide avec les clés (mets null si non précisé): "
           '{"intent":"offers|students|companies", "contract_type":"stage|alternance|null", '
           '"city":string|null, "region":string|null, "department":string|null, '
           '"domain":string|null, "skills":[string], "level":string|null, "naf_code":string|null, '
           '"keywords":string}.')
    try:
        raw = await call_ai(sys, text)
    except Exception as e:
        logger.error(f"AI search error: {e}")
        raise HTTPException(500, "Erreur IA")
    # Parse JSON (tolerant)
    import re, json as _json
    m = re.search(r"\{[\s\S]+\}", raw or "")
    criteria = {}
    if m:
        try: criteria = _json.loads(m.group(0))
        except Exception: criteria = {}
    # Log
    try:
        await db.ai_search_logs.insert_one({
            "log_id": f"ai_{uuid.uuid4().hex[:10]}",
            "user_id": user["user_id"] if user else None,
            "user_role": (user or {}).get("role"),
            "query_text": text,
            "criteria": criteria,
            "raw": (raw or "")[:1000],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
    return {"criteria": criteria, "raw": raw}


@phase_api.post("/me/search-history")
async def add_search_history(body: dict, user=Depends(get_current_user)):
    """Record a search performed by the user (if history enabled)."""
    if user.get("history_disabled"):
        return {"ok": True, "skipped": True}
    doc = {
        "id": f"sh_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "user_role": user.get("role"),
        "search_type": (body.get("search_type") or "offers"),
        "query_text": (body.get("query_text") or "")[:200],
        "filters": body.get("filters") or {},
        "results_count": int(body.get("results_count") or 0),
        "ai_generated": bool(body.get("ai_generated")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.search_history.insert_one(doc)
    doc.pop("_id", None)
    return doc


@phase_api.get("/me/search-history")
async def my_search_history(limit: int = 50, user=Depends(get_current_user)):
    items = await db.search_history.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(min(limit, 200)).to_list(limit)
    return items


@phase_api.delete("/me/search-history/{item_id}")
async def del_search_history_item(item_id: str, user=Depends(get_current_user)):
    r = await db.search_history.delete_one({"id": item_id, "user_id": user["user_id"]})
    return {"ok": True, "deleted": r.deleted_count}


@phase_api.delete("/me/search-history")
async def clear_search_history(user=Depends(get_current_user)):
    r = await db.search_history.delete_many({"user_id": user["user_id"]})
    return {"ok": True, "deleted": r.deleted_count}


@phase_api.patch("/me/history-settings")
async def set_history_disabled(body: dict, user=Depends(get_current_user)):
    disabled = bool(body.get("history_disabled", False))
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"history_disabled": disabled}})
    return {"ok": True, "history_disabled": disabled}


# ---------- Phase E: Admin API stats ----------
@phase_api.get("/admin/api-stats")
async def admin_api_stats(days: int = 30, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cur = db.api_request_logs.aggregate([
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$api_name",
            "calls": {"$sum": 1},
            "cache_hits": {"$sum": {"$cond": ["$cache_hit", 1, 0]}},
            "avg_ms": {"$avg": "$response_time_ms"},
            "errors": {"$sum": {"$cond": [{"$gte": ["$status", 400]}, 1, 0]}},
        }},
    ])
    by_api = [doc async for doc in cur]
    # Top search queries (companies API + AI)
    top_q = db.api_request_logs.aggregate([
        {"$match": {"created_at": {"$gte": cutoff}, "query.q": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$query.q", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 10},
    ])
    top_queries = [doc async for doc in top_q]
    top_dep = db.api_request_logs.aggregate([
        {"$match": {"created_at": {"$gte": cutoff}, "query.departement": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$query.departement", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 10},
    ])
    top_departments = [doc async for doc in top_dep]
    top_naf_c = db.api_request_logs.aggregate([
        {"$match": {"created_at": {"$gte": cutoff}, "query.activite_principale": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$query.activite_principale", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 10},
    ])
    top_naf = [doc async for doc in top_naf_c]
    ai_count = await db.ai_search_logs.count_documents({"created_at": {"$gte": cutoff}})
    profile_views_count = await db.profile_views.count_documents({"viewed_at": {"$gte": cutoff}})
    real_obtained = await db.applications.count_documents({"status": {"$in": list(OBTAINED_STATUSES)}})
    errors = await db.api_error_logs.find({"created_at": {"$gte": cutoff}}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {
        "window_days": days,
        "by_api": by_api,
        "top_queries": [{"q": x["_id"], "count": x["n"]} for x in top_queries],
        "top_departments": [{"department": x["_id"], "count": x["n"]} for x in top_departments],
        "top_naf": [{"naf": x["_id"], "count": x["n"]} for x in top_naf],
        "ai_searches": ai_count,
        "profile_views": profile_views_count,
        "obtained_count": real_obtained,
        "recent_errors": errors,
    }


app.include_router(phase_api)  # register Phase C/D/E endpoints


# ============ ITERATION 10: La Bonne Alternance integration ============
from labonnealternance import search_alternance as lba_search

lba_api = APIRouter(prefix="/api")

CITY_TO_GEO = {
    "paris": (48.8566, 2.3522), "lyon": (45.7640, 4.8357), "marseille": (43.2965, 5.3698),
    "toulouse": (43.6047, 1.4442), "nice": (43.7102, 7.2620), "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521), "montpellier": (43.6112, 3.8767), "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573), "rennes": (48.1173, -1.6778), "reims": (49.2583, 4.0317),
    "toulon": (43.1242, 5.9280), "saint-étienne": (45.4397, 4.3872), "le havre": (49.4944, 0.1079),
    "grenoble": (45.1885, 5.7245), "dijon": (47.3220, 5.0415), "angers": (47.4784, -0.5632),
    "nîmes": (43.8367, 4.3601), "villeurbanne": (45.7665, 4.8795),
    "valence": (44.9333, 4.8920), "perpignan": (42.6886, 2.8946),
}


def _resolve_geo(city: Optional[str], lat: Optional[float], lon: Optional[float]):
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    if city:
        key = city.strip().lower()
        if key in CITY_TO_GEO:
            return CITY_TO_GEO[key]
    return None, None


@lba_api.get("/lba/search")
async def alternance_search(
    city: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius: int = 30,
    romes: Optional[str] = None,
    per_page: int = 30,
    user=Depends(get_optional_user),
):
    """Search apprenticeship/alternance offers via La Bonne Alternance (official gouv API)."""
    lat, lon = _resolve_geo(city, latitude, longitude)
    if lat is None:
        lat, lon = 48.8566, 2.3522  # default Paris
    return await lba_search(
        db, latitude=lat, longitude=lon, radius=radius,
        romes=romes or DEFAULT_LBA_ROMES, per_page=per_page,
    )


@lba_api.delete("/admin/lba-cache")
async def admin_clear_lba_cache(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    r = await db.lba_search_cache.delete_many({})
    return {"ok": True, "deleted": r.deleted_count}


DEFAULT_LBA_ROMES = "M1805,M1810,M1802,M1803,E1101,E1103,K1207,K1801,M1707,M1701,M1402,M1502"

app.include_router(lba_api)


# ============ ITERATION 11: France Travail (Offres v2) ============
from francetravail import search_offers as ft_search

ft_api = APIRouter(prefix="/api")

CITY_TO_DEPT = {
    "paris": "75", "lyon": "69", "marseille": "13", "toulouse": "31",
    "nice": "06", "nantes": "44", "strasbourg": "67", "montpellier": "34",
    "bordeaux": "33", "lille": "59", "rennes": "35", "reims": "51",
    "toulon": "83", "saint-étienne": "42", "le havre": "76",
    "grenoble": "38", "dijon": "21", "angers": "49", "nîmes": "30",
    "villeurbanne": "69", "valence": "26", "perpignan": "66",
    "ile-de-france": "75", "île-de-france": "75", "auvergne-rhône-alpes": "69",
}


def _resolve_ft_dept(city: Optional[str], region: Optional[str], dept: Optional[str]) -> Optional[str]:
    if dept: return dept[:2]
    if city:
        key = city.strip().lower()
        if key in CITY_TO_DEPT: return CITY_TO_DEPT[key]
    if region:
        key = region.strip().lower()
        if key in CITY_TO_DEPT: return CITY_TO_DEPT[key]
    return None


@ft_api.get("/francetravail/search")
async def francetravail_search(
    city: Optional[str] = None,
    region: Optional[str] = None,
    departement: Optional[str] = None,
    domain: Optional[str] = None,
    q: Optional[str] = None,
    nature: str = "E2,FS",
    per_page: int = 30,
):
    """Search alternance/stage offers from France Travail (Pôle Emploi)."""
    dept = _resolve_ft_dept(city, region, departement)
    if not dept:
        dept = "75"  # default Paris if nothing specified
    return await ft_search(
        db,
        departement=dept,
        mots_cles=q,
        domain=domain,
        nature_contrat=nature,
        per_page=per_page,
    )


@ft_api.delete("/admin/ft-cache")
async def admin_clear_ft_cache(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    r = await db.ft_search_cache.delete_many({})
    return {"ok": True, "deleted": r.deleted_count}


app.include_router(ft_api)


# ============ Feature routers (split from server.py for maintainability) ============
from ads_routes import register_ads_routes
from routes.posts import register_posts_routes
from routes.messages import register_messages_routes
from routes.contacts import register_contacts_routes
from routes.notifications import register_notifications_routes
from routes.deals import register_deals_routes
from routes.moderation import register_moderation_routes

ads_router = APIRouter(prefix="/api")
register_ads_routes(ads_router, db, get_current_user, notify, company_subscription_active)
app.include_router(ads_router)

posts_router = APIRouter(prefix="/api")
register_posts_routes(posts_router, db, get_current_user, notify)
app.include_router(posts_router)

messages_router = APIRouter(prefix="/api")
register_messages_routes(messages_router, db, get_current_user, notify)
app.include_router(messages_router)

contacts_router = APIRouter(prefix="/api")
register_contacts_routes(contacts_router, db, get_current_user, notify)
app.include_router(contacts_router)

notifications_router = APIRouter(prefix="/api")
register_notifications_routes(notifications_router, db, get_current_user)
app.include_router(notifications_router)

deals_router = APIRouter(prefix="/api")
register_deals_routes(deals_router, db, get_current_user, notify)
app.include_router(deals_router)

moderation_router = APIRouter(prefix="/api")
register_moderation_routes(moderation_router, db, get_current_user, notify)
app.include_router(moderation_router)


# ============ ITERATION 12: External Sources Aggregator + Diploma Levels + Cleanup ============
from external_sources import (
    fetch_all_keyless,
    fetch_ashby, fetch_arbeitnow, fetch_remotive, fetch_remoteok, fetch_jobicy, fetch_greenhouse,
)
from external_keyed import (
    fetch_all_keyed,
    fetch_adzuna, fetch_jooble, fetch_eures_apify,
)

ext_offers_api = APIRouter(prefix="/api")

DIPLOMA_LEVELS = [
    "Sans diplôme requis",
    "Collège",
    "Stage de 3e",
    "CAP",
    "BEP",
    "Bac général",
    "Bac technologique",
    "Bac professionnel",
    "Mention complémentaire",
    "BP",
    "BMA",
    "Bac +1",
    "BTS",
    "BTSA",
    "DUT",
    "BUT",
    "DEUST",
    "Licence",
    "Licence professionnelle",
    "Bachelor",
    "Bac +2",
    "Bac +3",
    "Bac +4",
    "Master 1",
    "Master 2",
    "Bac +5",
    "Diplôme d'ingénieur",
    "MBA",
    "Mastère spécialisé",
    "Doctorat",
    "Reconversion professionnelle",
    "Formation courte",
    "Formation adulte",
]


@ext_offers_api.get("/diploma-levels")
async def diploma_levels():
    return {"levels": DIPLOMA_LEVELS}


SOURCE_PRIORITY = {
    "StageConnect": 10, "StageEtudiant": 10,
    "FranceTravail": 8, "La Bonne Alternance": 8,
    "Ashby": 5, "Greenhouse": 5,
    "Adzuna": 5, "Jooble": 5,
    "Arbeitnow": 4, "Remotive": 4, "RemoteOK": 4, "Jobicy": 4,
    "EURES": 4,
}


def _compute_priority(o: dict) -> int:
    return SOURCE_PRIORITY.get(o.get("source"), 1) + (10 if not o.get("is_external") else 0)


@ext_offers_api.get("/external-offers/keyless")
async def get_keyless_offers(force_refresh: bool = False):
    return await fetch_all_keyless(db, force_refresh=force_refresh)


@ext_offers_api.get("/external-offers/keyed")
async def get_keyed_offers(
    force_refresh: bool = False,
    what: str = "stage alternance",
    where: str = "France",
):
    """Aggregated Adzuna + Jooble + EURES (Apify) offers, cached 12h."""
    return await fetch_all_keyed(db, force_refresh=force_refresh, what=what, where=where)


@ext_offers_api.get("/external-offers/all")
async def get_all_external_offers(force_refresh: bool = False):
    """Aggregate keyless + keyed external sources in one call (parallel)."""
    keyless, keyed = await asyncio.gather(
        fetch_all_keyless(db, force_refresh=force_refresh),
        fetch_all_keyed(db, force_refresh=force_refresh),
        return_exceptions=True,
    )
    keyless = keyless if isinstance(keyless, dict) else {"results": [], "by_source": {}}
    keyed = keyed if isinstance(keyed, dict) else {"results": [], "by_source": {}}
    merged: list = []
    seen: set = set()
    for o in (keyless.get("results", []) + keyed.get("results", [])):
        k = o.get("external_url") or o.get("offer_id")
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        merged.append(o)
    by_source = {**keyless.get("by_source", {}), **keyed.get("by_source", {})}
    return {
        "results": merged,
        "by_source": by_source,
        "cache_hit": bool(keyless.get("cache_hit") and keyed.get("cache_hit")),
    }


@ext_offers_api.post("/admin/ashby-boards")
async def add_ashby_board(body: dict, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    token = (body.get("board_token") or "").strip()
    if not token:
        raise HTTPException(400, "board_token requis")
    doc = {
        "board_token": token,
        "company_name": body.get("company_name") or token,
        "active": bool(body.get("active", True)),
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ashby_boards.update_one({"board_token": token}, {"$set": doc}, upsert=True)
    return doc


@ext_offers_api.get("/admin/ashby-boards")
async def list_ashby_boards(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return await db.ashby_boards.find({}, {"_id": 0}).to_list(100)


@ext_offers_api.delete("/admin/ashby-boards/{token}")
async def del_ashby_board(token: str, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    r = await db.ashby_boards.delete_one({"board_token": token})
    return {"ok": True, "deleted": r.deleted_count}


@ext_offers_api.post("/admin/greenhouse-boards")
async def add_gh_board(body: dict, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    token = (body.get("board_token") or "").strip()
    if not token:
        raise HTTPException(400, "board_token requis")
    doc = {
        "board_token": token,
        "company_name": body.get("company_name") or token,
        "active": bool(body.get("active", True)),
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.greenhouse_boards.update_one({"board_token": token}, {"$set": doc}, upsert=True)
    return doc


@ext_offers_api.get("/admin/greenhouse-boards")
async def list_gh_boards(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return await db.greenhouse_boards.find({}, {"_id": 0}).to_list(100)


@ext_offers_api.delete("/admin/greenhouse-boards/{token}")
async def del_gh_board(token: str, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    r = await db.greenhouse_boards.delete_one({"board_token": token})
    return {"ok": True, "deleted": r.deleted_count}


@ext_offers_api.delete("/admin/external-offers-cache")
async def del_ext_offers_cache(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    r = await db.external_offers_cache.delete_many({})
    return {"ok": True, "deleted": r.deleted_count}


@ext_offers_api.get("/admin/external-sources-status")
async def external_sources_status(user=Depends(get_current_user)):
    """Returns each source state: active flag (env), last fetch, errors, offer count in cache."""
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    cache_doc = await db.external_offers_cache.find_one({"key": "keyless_all"}, {"_id": 0}) or {}
    sources = []
    for name in ["Ashby", "Arbeitnow", "Remotive", "RemoteOK", "Jobicy", "Greenhouse",
                 "FranceTravail", "La Bonne Alternance", "Adzuna", "Jooble", "EURES"]:
        recent = await db.api_request_logs.find_one(
            {"api_name": {"$regex": name.lower().replace(" ", "")}}, {"_id": 0}, sort=[("created_at", -1)]
        )
        recent_err = await db.api_error_logs.find_one(
            {"api_name": {"$regex": name.lower().replace(" ", "")}}, {"_id": 0}, sort=[("created_at", -1)]
        )
        env_key = f"ENABLE_{name.upper().replace(' ', '_')}"
        sources.append({
            "name": name,
            "enabled": os.environ.get(env_key, "true").lower() in ("true", "1", "yes"),
            "last_call": (recent or {}).get("created_at"),
            "last_status": (recent or {}).get("status"),
            "last_error_at": (recent_err or {}).get("created_at"),
            "last_error": (recent_err or {}).get("error"),
            "cached_count": cache_doc.get("by_source", {}).get(name, 0),
            "requires_key": name in ("Adzuna", "Jooble", "EURES"),
        })
    return {
        "sources": sources,
        "cache": {
            "cached_at": cache_doc.get("cached_at"),
            "expires_at": cache_doc.get("expires_at"),
            "total_offers": len(cache_doc.get("results", [])),
        },
    }


app.include_router(ext_offers_api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup():
    # Auto-seed once
    if await db.users.count_documents({}) < 3:
        try:
            await seed(force=True)
            logger.info("Database seeded")
        except Exception as e:
            logger.error(f"Seed failed: {e}")
    # Auto-seed-v3 massive (offers) once
    if await db.offers.count_documents({}) < 50:
        try:
            await seed_v3(force=True)
            logger.info("Database v3 seeded (100+ companies, 300+ offers)")
        except Exception as e:
            logger.error(f"Seed-v3 failed: {e}")
    # Init storage
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.warning(f"Storage init deferred: {e}")
    # Mongo indexes
    await ensure_indexes()

@app.on_event("shutdown")
async def shutdown():
    client.close()
