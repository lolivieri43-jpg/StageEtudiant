"""Shared Pydantic models — single source of truth for cross-cutting payloads.

Imported by:
- /app/backend/server.py        (for inline /messages-rt and other endpoints still living there)
- /app/backend/routes/posts.py
- /app/backend/routes/messages.py
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


# ---------- POSTS / FEED ----------
class PostMedia(BaseModel):
    type: str  # image | video | pdf
    url: str
    file_id: Optional[str] = None
    filename: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    poster: Optional[str] = None


class LinkPreview(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    domain: Optional[str] = None


class PostIn(BaseModel):
    content: str
    image: Optional[str] = None
    category: Optional[str] = "general"
    media: List[PostMedia] = []
    link_preview: Optional[LinkPreview] = None


class CommentIn(BaseModel):
    post_id: str
    content: str


# ---------- APPLICATIONS ----------
class ApplicationIn(BaseModel):
    offer_id: str
    cover_letter: Optional[str] = None
    use_online_cv: bool = True
    online_cv_template: Optional[str] = "modern"
    uploaded_doc_ids: List[str] = []


# ---------- MESSAGES ----------
class MessageAttachment(BaseModel):
    type: str  # image | video | pdf | doc | file
    url: str
    file_id: Optional[str] = None
    filename: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = None


class MessageIn(BaseModel):
    to_user_id: str
    content: str
    attachment: Optional[str] = None
    attachments: List[MessageAttachment] = []


# ---------- CONTACTS ----------
class ContactRequestIn(BaseModel):
    to_user_id: str


# ---------- DEALS ----------
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
