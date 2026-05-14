"""FastAPI backend for StagiaireConnect - French stage/alternance platform."""
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

app = FastAPI(title="StagiaireConnect API")
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

class PostIn(BaseModel):
    content: str
    image: Optional[str] = None
    category: Optional[str] = "general"  # annonce, recherche, conseil, general

class CommentIn(BaseModel):
    post_id: str
    content: str

class MessageIn(BaseModel):
    to_user_id: str
    content: str
    attachment: Optional[str] = None

class ContactRequestIn(BaseModel):
    to_user_id: str

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
async def get_user_public(user_id: str):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password": 0})
    if not u:
        raise HTTPException(404, "Utilisateur introuvable")
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
    offers = await db.offers.find(query, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500)).to_list(min(limit, 500))
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

# ============ POSTS / FEED ============
@api.post("/posts")
async def create_post(data: PostIn, user=Depends(get_current_user)):
    post_id = f"post_{uuid.uuid4().hex[:12]}"
    doc = {
        "post_id": post_id,
        "author_id": user["user_id"],
        "author_name": user["name"],
        "author_role": user["role"],
        "author_avatar": user.get("profile", {}).get("avatar") or user.get("profile", {}).get("logo"),
        "content": data.content,
        "image": data.image,
        "category": data.category,
        "likes": [],
        "comments_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.posts.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/posts")
async def list_posts(limit: int = 30):
    posts = await db.posts.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return posts

@api.post("/posts/{post_id}/like")
async def like_post(post_id: str, user=Depends(get_current_user)):
    post = await db.posts.find_one({"post_id": post_id})
    if not post:
        raise HTTPException(404, "Introuvable")
    likes = post.get("likes", [])
    if user["user_id"] in likes:
        likes.remove(user["user_id"])
    else:
        likes.append(user["user_id"])
        if post["author_id"] != user["user_id"]:
            await notify(post["author_id"], "like", f"{user['name']} a aimé votre publication", "/feed")
    await db.posts.update_one({"post_id": post_id}, {"$set": {"likes": likes}})
    return {"likes": likes}

@api.post("/posts/comment")
async def add_comment(data: CommentIn, user=Depends(get_current_user)):
    post = await db.posts.find_one({"post_id": data.post_id})
    if not post:
        raise HTTPException(404, "Post introuvable")
    cid = f"c_{uuid.uuid4().hex[:10]}"
    doc = {
        "comment_id": cid,
        "post_id": data.post_id,
        "author_id": user["user_id"],
        "author_name": user["name"],
        "author_avatar": user.get("profile", {}).get("avatar") or user.get("profile", {}).get("logo"),
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.comments.insert_one(doc)
    await db.posts.update_one({"post_id": data.post_id}, {"$inc": {"comments_count": 1}})
    if post["author_id"] != user["user_id"]:
        await notify(post["author_id"], "comment", f"{user['name']} a commenté votre publication", "/feed")
    doc.pop("_id", None)
    return doc

@api.get("/posts/{post_id}/comments")
async def get_comments(post_id: str):
    cs = await db.comments.find({"post_id": post_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return cs

# ============ MESSAGES ============
@api.post("/messages")
async def send_message(data: MessageIn, user=Depends(get_current_user)):
    other = await db.users.find_one({"user_id": data.to_user_id}, {"_id": 0})
    if not other:
        raise HTTPException(404, "Destinataire introuvable")
    pair = sorted([user["user_id"], data.to_user_id])
    conv_id = f"conv_{pair[0][-6:]}_{pair[1][-6:]}"
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "message_id": msg_id,
        "conv_id": conv_id,
        "from_id": user["user_id"],
        "from_name": user["name"],
        "to_id": data.to_user_id,
        "to_name": other["name"],
        "content": data.content,
        "attachment": data.attachment,
        "read": False,
        "created_at": now,
    }
    await db.messages.insert_one(doc)
    await db.conversations.update_one(
        {"conv_id": conv_id},
        {"$set": {
            "conv_id": conv_id,
            "participants": pair,
            "last_message": data.content,
            "last_at": now,
        }},
        upsert=True,
    )
    await notify(data.to_user_id, "message", f"Nouveau message de {user['name']}", "/messages", {"user_id": user["user_id"], "name": user["name"]})
    doc.pop("_id", None)
    return doc

@api.get("/conversations")
async def list_conversations(user=Depends(get_current_user)):
    convs = await db.conversations.find({"participants": user["user_id"]}, {"_id": 0}).sort("last_at", -1).to_list(100)
    # enrich with other participant
    result = []
    for c in convs:
        other_id = next((p for p in c["participants"] if p != user["user_id"]), None)
        if not other_id:
            continue
        other = await db.users.find_one({"user_id": other_id}, {"_id": 0, "password": 0})
        unread = await db.messages.count_documents({"conv_id": c["conv_id"], "to_id": user["user_id"], "read": False})
        result.append({**c, "other": other, "unread": unread})
    return result

@api.get("/messages/{other_user_id}")
async def get_messages(other_user_id: str, user=Depends(get_current_user)):
    pair = sorted([user["user_id"], other_user_id])
    conv_id = f"conv_{pair[0][-6:]}_{pair[1][-6:]}"
    msgs = await db.messages.find({"conv_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    await db.messages.update_many({"conv_id": conv_id, "to_id": user["user_id"]}, {"$set": {"read": True}})
    return msgs

# ============ CONTACTS ============
@api.post("/contacts/request")
async def request_contact(data: ContactRequestIn, user=Depends(get_current_user)):
    if data.to_user_id == user["user_id"]:
        raise HTTPException(400, "Impossible")
    existing = await db.contact_requests.find_one({"from_id": user["user_id"], "to_id": data.to_user_id, "status": "pending"})
    if existing:
        raise HTTPException(400, "Demande déjà envoyée")
    other = await db.users.find_one({"user_id": data.to_user_id}, {"_id": 0})
    if not other:
        raise HTTPException(404, "Introuvable")
    rid = f"cr_{uuid.uuid4().hex[:10]}"
    await db.contact_requests.insert_one({
        "request_id": rid,
        "from_id": user["user_id"],
        "from_name": user["name"],
        "from_avatar": user.get("profile", {}).get("avatar") or user.get("profile", {}).get("logo"),
        "to_id": data.to_user_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await notify(data.to_user_id, "contact_request", f"{user['name']} souhaite ajouter en contact", "/contacts", {"user_id": user["user_id"], "name": user["name"]})
    return {"ok": True, "request_id": rid}

@api.post("/contacts/{request_id}/accept")
async def accept_contact(request_id: str, user=Depends(get_current_user)):
    req = await db.contact_requests.find_one({"request_id": request_id})
    if not req or req["to_id"] != user["user_id"]:
        raise HTTPException(404, "Introuvable")
    await db.contact_requests.update_one({"request_id": request_id}, {"$set": {"status": "accepted"}})
    pair = sorted([req["from_id"], req["to_id"]])
    await db.contacts.insert_one({
        "contact_id": f"ct_{uuid.uuid4().hex[:10]}",
        "user_a": pair[0],
        "user_b": pair[1],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await notify(req["from_id"], "contact_accepted", f"{user['name']} a accepté votre demande de contact", "/contacts")
    return {"ok": True}

@api.post("/contacts/{request_id}/refuse")
async def refuse_contact(request_id: str, user=Depends(get_current_user)):
    req = await db.contact_requests.find_one({"request_id": request_id})
    if not req or req["to_id"] != user["user_id"]:
        raise HTTPException(404, "Introuvable")
    await db.contact_requests.update_one({"request_id": request_id}, {"$set": {"status": "refused"}})
    return {"ok": True}

@api.get("/contacts")
async def list_contacts(user=Depends(get_current_user)):
    cs = await db.contacts.find({"$or": [{"user_a": user["user_id"]}, {"user_b": user["user_id"]}]}, {"_id": 0}).to_list(200)
    pending = await db.contact_requests.find({"to_id": user["user_id"], "status": "pending"}, {"_id": 0}).to_list(50)
    sent = await db.contact_requests.find({"from_id": user["user_id"], "status": "pending"}, {"_id": 0}).to_list(50)
    contacts = []
    for c in cs:
        other_id = c["user_b"] if c["user_a"] == user["user_id"] else c["user_a"]
        other = await db.users.find_one({"user_id": other_id}, {"_id": 0, "password": 0})
        if other:
            contacts.append(other)
    return {"contacts": contacts, "pending": pending, "sent": sent}

# ============ NOTIFICATIONS ============
@api.get("/notifications")
async def list_notifs(user=Depends(get_current_user)):
    n = await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    unread = sum(1 for x in n if not x.get("read"))
    return {"notifications": n, "unread": unread}

@api.post("/notifications/read")
async def mark_read(user=Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}

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
    return {"name": "StagiaireConnect API", "status": "ok"}

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

DealStatus = Literal["draft", "pending", "published", "refused", "expired"]

class DealIn(BaseModel):
    title: str
    description: str
    category: Optional[str] = "general"  # food, sport, culture, transport, study, fashion, tech
    city: Optional[str] = None
    region: Optional[str] = None
    image: Optional[str] = None
    promo_code: Optional[str] = None
    discount: Optional[str] = None  # "-20%", "Gratuit", "10€ offerts"
    url: Optional[str] = None
    expires_at: Optional[str] = None  # ISO date

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

@api.post("/deals")
async def create_deal(data: DealIn, user=Depends(get_current_user)):
    if user["role"] == "company":
        if not await company_subscription_active(user["user_id"]):
            raise HTTPException(402, "Abonnement Pro Bons Plans requis pour publier")
        status = "published"
    else:
        status = "pending"  # student: needs admin validation
    deal_id = f"deal_{uuid.uuid4().hex[:12]}"
    doc = {
        "deal_id": deal_id,
        "author_id": user["user_id"],
        "author_name": user["name"],
        "author_type": user["role"],
        "author_avatar": user.get("profile", {}).get("avatar") or user.get("profile", {}).get("logo"),
        **data.model_dump(),
        "status": status,
        "boosted_until": None,
        "sponsored_until": None,
        "views": 0,
        "clicks": 0,
        "saves": [],
        "shares": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.deals.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/deals")
async def list_deals(
    q: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    author_type: Optional[str] = None,
    status: Optional[str] = "published",
    limit: int = 60,
):
    query = {}
    if status:
        query["status"] = status
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if category: query["category"] = category
    if region: query["region"] = region
    if city: query["city"] = {"$regex": city, "$options": "i"}
    if author_type: query["author_type"] = author_type
    deals = await db.deals.find(query, {"_id": 0}).to_list(limit)
    now = datetime.now(timezone.utc)
    def tier(d):
        s = d.get("sponsored_until")
        b = d.get("boosted_until")
        if s and datetime.fromisoformat(s).replace(tzinfo=timezone.utc) > now: return 0
        if b and datetime.fromisoformat(b).replace(tzinfo=timezone.utc) > now: return 1
        return 2
    deals.sort(key=lambda d: (tier(d), d.get("created_at", ""), ), reverse=False)
    # Then reverse-sort by date within same tier
    deals.sort(key=lambda d: (tier(d), -datetime.fromisoformat(d["created_at"]).timestamp()))
    return deals

@api.get("/deals/mine")
async def my_deals(user=Depends(get_current_user)):
    deals = await db.deals.find({"author_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    saved_ids = []
    for d in await db.deals.find({"saves": user["user_id"]}, {"_id": 0, "deal_id": 1}).to_list(200):
        saved_ids.append(d["deal_id"])
    saved = await db.deals.find({"deal_id": {"$in": saved_ids}}, {"_id": 0}).to_list(200)
    boosts = await db.boost_orders.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"deals": deals, "saved": saved, "boosts": boosts}

@api.get("/deals/{deal_id}")
async def get_deal(deal_id: str):
    d = await db.deals.find_one({"deal_id": deal_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Bon plan introuvable")
    await db.deals.update_one({"deal_id": deal_id}, {"$inc": {"views": 1}})
    d["views"] = d.get("views", 0) + 1
    return d

@api.patch("/deals/{deal_id}")
async def update_deal(deal_id: str, data: dict, user=Depends(get_current_user)):
    d = await db.deals.find_one({"deal_id": deal_id})
    if not d:
        raise HTTPException(404, "Introuvable")
    if d["author_id"] != user["user_id"] and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    if d["author_type"] == "company" and user["role"] != "admin":
        if not await company_subscription_active(user["user_id"]):
            raise HTTPException(402, "Abonnement requis")
    allowed = {"title", "description", "category", "city", "region", "image", "promo_code", "discount", "url", "expires_at"}
    upd = {k: v for k, v in data.items() if k in allowed}
    if upd:
        await db.deals.update_one({"deal_id": deal_id}, {"$set": upd})
    return {"ok": True}

@api.delete("/deals/{deal_id}")
async def delete_deal(deal_id: str, user=Depends(get_current_user)):
    d = await db.deals.find_one({"deal_id": deal_id})
    if not d:
        raise HTTPException(404, "Introuvable")
    if d["author_id"] != user["user_id"] and user["role"] != "admin":
        raise HTTPException(403, "Interdit")
    await db.deals.delete_one({"deal_id": deal_id})
    return {"ok": True}

@api.post("/deals/{deal_id}/save")
async def save_deal(deal_id: str, user=Depends(get_current_user)):
    d = await db.deals.find_one({"deal_id": deal_id})
    if not d:
        raise HTTPException(404, "Introuvable")
    saves = d.get("saves", [])
    if user["user_id"] in saves:
        saves.remove(user["user_id"])
    else:
        saves.append(user["user_id"])
        if d["author_id"] != user["user_id"]:
            await notify(d["author_id"], "deal_save", f"{user['name']} a sauvegardé votre bon plan \"{d['title']}\"", f"/deals/{deal_id}")
    await db.deals.update_one({"deal_id": deal_id}, {"$set": {"saves": saves}})
    return {"saves": saves}

@api.post("/deals/{deal_id}/click")
async def click_deal(deal_id: str):
    await db.deals.update_one({"deal_id": deal_id}, {"$inc": {"clicks": 1}})
    return {"ok": True}

@api.post("/deals/{deal_id}/share")
async def share_deal(deal_id: str):
    await db.deals.update_one({"deal_id": deal_id}, {"$inc": {"shares": 1}})
    return {"ok": True}

# Admin: validation
@api.post("/admin/deals/{deal_id}/validate")
async def validate_deal(deal_id: str, body: dict, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin")
    action = body.get("action")  # "approve" / "refuse" / "disable"
    deal = await db.deals.find_one({"deal_id": deal_id})
    if not deal:
        raise HTTPException(404, "Introuvable")
    new_status = {"approve": "published", "refuse": "refused", "disable": "expired"}.get(action)
    if not new_status:
        raise HTTPException(400, "Action invalide")
    await db.deals.update_one({"deal_id": deal_id}, {"$set": {"status": new_status}})
    await notify(deal["author_id"], "deal_validation", f"Votre bon plan \"{deal['title']}\" est {new_status}", f"/deals/{deal_id}")
    return {"ok": True}

@api.get("/admin/deals/pending")
async def admin_pending_deals(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin")
    return await db.deals.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)

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
        "webp": "image/webp", "pdf": "application/pdf"}

@api.post("/upload")
async def upload_file(file: UploadFile = File(...), kind: str = "doc", user=Depends(get_current_user)):
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin").lower()
    if ext not in MIME:
        raise HTTPException(400, f"Type non supporté: {ext}")
    file_id = uuid.uuid4().hex
    path = f"{APP_NAME}/{user['user_id']}/{file_id}.{ext}"
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Fichier trop volumineux (max 8 Mo)")
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
            {"id": "StageConnect", "label": "StageConnect", "internal": True},
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
    allowed = {"vue", "en_analyse", "entretien_propose", "acceptee", "refusee", "archivee"}
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

# ============ CONTACT EXTENSIONS: cancel sent, block ============
@api.delete("/contacts/request/{request_id}")
async def cancel_contact_request(request_id: str, user=Depends(get_current_user)):
    r = await db.contact_requests.find_one({"request_id": request_id})
    if not r or r["from_id"] != user["user_id"]:
        raise HTTPException(403, "Interdit")
    await db.contact_requests.delete_one({"request_id": request_id})
    return {"ok": True}

@api.delete("/contacts/{contact_user_id}")
async def remove_contact(contact_user_id: str, user=Depends(get_current_user)):
    await db.contacts.delete_many({"$or": [
        {"user_a": user["user_id"], "user_b": contact_user_id},
        {"user_a": contact_user_id, "user_b": user["user_id"]},
    ]})
    return {"ok": True}

@api.post("/contacts/block/{target_id}")
async def block_user(target_id: str, user=Depends(get_current_user)):
    existing = await db.blocked_users.find_one({"blocker_id": user["user_id"], "blocked_id": target_id})
    if existing:
        return {"ok": True, "already_blocked": True}
    await db.blocked_users.insert_one({
        "block_id": f"b_{uuid.uuid4().hex[:10]}",
        "blocker_id": user["user_id"], "blocked_id": target_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.contacts.delete_many({"$or": [
        {"user_a": user["user_id"], "user_b": target_id},
        {"user_a": target_id, "user_b": user["user_id"]},
    ]})
    return {"ok": True}

# Contact status helper for frontend
@api.get("/contacts/status/{other_id}")
async def contact_status(other_id: str, user=Depends(get_current_user)):
    if other_id == user["user_id"]:
        return {"status": "self"}
    c = await db.contacts.find_one({"$or": [
        {"user_a": user["user_id"], "user_b": other_id},
        {"user_a": other_id, "user_b": user["user_id"]},
    ]})
    if c:
        return {"status": "connected"}
    sent = await db.contact_requests.find_one({"from_id": user["user_id"], "to_id": other_id, "status": "pending"}, {"_id": 0})
    if sent:
        return {"status": "sent", "request_id": sent["request_id"]}
    received = await db.contact_requests.find_one({"from_id": other_id, "to_id": user["user_id"], "status": "pending"}, {"_id": 0})
    if received:
        return {"status": "received", "request_id": received["request_id"]}
    return {"status": "none"}

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
    doc = {
        "message_id": msg_id, "conv_id": conv_id,
        "from_id": user["user_id"], "from_name": user["name"],
        "to_id": data.to_user_id, "to_name": other["name"],
        "content": data.content, "attachment": data.attachment,
        "read": False, "created_at": now,
    }
    await db.messages.insert_one(doc)
    doc.pop("_id", None)
    await db.conversations.update_one(
        {"conv_id": conv_id},
        {"$set": {"conv_id": conv_id, "participants": pair, "last_message": data.content, "last_at": now}},
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



app.include_router(api)

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

@app.on_event("shutdown")
async def shutdown():
    client.close()
