"""Posts / Feed routes — split from server.py for maintainability.
Endpoints:
- POST /api/posts           — create a post with media + link_preview
- GET  /api/posts           — list latest posts
- POST /api/posts/link-preview — fetch Open Graph metadata (cached 7d)
- POST /api/posts/{id}/like — toggle like
- POST /api/posts/comment   — add comment
- GET  /api/posts/{id}/comments — list comments
"""
from __future__ import annotations

import asyncio
import re as _re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from models import PostIn, CommentIn  # noqa: F401 — shared models


def register_posts_routes(api_router, db, get_current_user, notify):
    @api_router.post("/posts")
    async def create_post(data: PostIn, user=Depends(get_current_user)):
        post_id = f"post_{uuid.uuid4().hex[:12]}"
        media = [m.model_dump() for m in (data.media or [])]
        if data.image and not media:
            media.append({"type": "image", "url": data.image, "file_id": None,
                          "filename": None, "mime": None, "size": None})
        doc = {
            "post_id": post_id,
            "author_id": user["user_id"],
            "author_name": user["name"],
            "author_role": user["role"],
            "author_avatar": user.get("profile", {}).get("avatar") or user.get("profile", {}).get("logo"),
            "content": data.content,
            "image": data.image,
            "media": media,
            "link_preview": data.link_preview.model_dump() if data.link_preview else None,
            "category": data.category,
            "likes": [],
            "comments_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.posts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @api_router.post("/posts/link-preview")
    async def fetch_link_preview(body: dict, user=Depends(get_current_user)):
        url = (body.get("url") or "").strip()
        if not url:
            raise HTTPException(400, "URL requise")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        cache = await db.link_preview_cache.find_one({"url": url}, {"_id": 0})
        if cache:
            return cache

        def _do_fetch():
            import requests as _rq
            return _rq.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 StageEtudiant-LinkPreview/1.0"},
                timeout=8,
                allow_redirects=True,
            )

        try:
            r = await asyncio.to_thread(_do_fetch)
            html = r.text[:300000]
        except Exception as e:
            raise HTTPException(400, f"Impossible de récupérer la page: {e}")

        def og(prop):
            m = _re.search(rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']+)["\']', html, _re.I)
            return m.group(1) if m else None

        def meta_name(name):
            m = _re.search(rf'<meta[^>]+name=["\']{name}["\'][^>]+content=["\']([^"\']+)["\']', html, _re.I)
            return m.group(1) if m else None

        title_match = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.I)
        title = og("title") or (title_match.group(1).strip() if title_match else None)
        description = og("description") or meta_name("description")
        image = og("image")
        if image and image.startswith("//"):
            image = "https:" + image
        elif image and image.startswith("/"):
            p = urlparse(url)
            image = f"{p.scheme}://{p.netloc}{image}"
        parsed = urlparse(url)
        preview = {
            "url": url,
            "title": (title or "")[:200] or None,
            "description": (description or "")[:300] or None,
            "image": image,
            "domain": parsed.netloc,
        }
        await db.link_preview_cache.update_one(
            {"url": url},
            {"$set": {**preview, "cached_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return preview

    @api_router.get("/posts")
    async def list_posts(limit: int = 30):
        return await db.posts.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)

    @api_router.post("/posts/{post_id}/like")
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
                await notify(post["author_id"], "like",
                             f"{user['name']} a aimé votre publication", "/feed")
        await db.posts.update_one({"post_id": post_id}, {"$set": {"likes": likes}})
        return {"likes": likes}

    @api_router.post("/posts/comment")
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
            await notify(post["author_id"], "comment",
                         f"{user['name']} a commenté votre publication", "/feed")
        doc.pop("_id", None)
        return doc

    @api_router.get("/posts/{post_id}/comments")
    async def get_comments(post_id: str):
        return await db.comments.find({"post_id": post_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
