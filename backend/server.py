"""FastAPI backend for StagiaireConnect - French stage/alternance platform."""
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import requests
from collections import Counter

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
    limit: int = 50,
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
    offers = await db.offers.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
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

@app.on_event("shutdown")
async def shutdown():
    client.close()
