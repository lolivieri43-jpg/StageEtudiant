"""Storage / Upload routes — split from server.py.

Endpoints:
- POST /api/upload          — upload a file (multipart) → returns file_id + url
- GET  /api/files/{file_id} — download a file with access control by kind/visibility
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import Depends, File, Header, HTTPException, Query, Request, Response, UploadFile


STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = os.environ.get("APP_NAME", "stagiaireconnect")
_storage_key: Optional[str] = None


def _init_storage() -> str:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_KEY:
        raise HTTPException(500, "Storage non configuré")
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    key = _init_storage()
    r = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _get_object(path: str):
    key = _init_storage()
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "webp": "image/webp", "pdf": "application/pdf",
    "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
MAX_BYTES = {
    "image/jpeg": 8 * 1024 * 1024, "image/png": 8 * 1024 * 1024,
    "image/gif": 8 * 1024 * 1024, "image/webp": 8 * 1024 * 1024,
    "application/pdf": 15 * 1024 * 1024,
    "video/mp4": 50 * 1024 * 1024, "video/webm": 50 * 1024 * 1024,
    "video/quicktime": 50 * 1024 * 1024,
}
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def register_storage_routes(api_router, db, get_current_user):
    @api_router.post("/upload")
    async def upload_file(file: UploadFile = File(...), kind: str = "doc",
                          user=Depends(get_current_user)):
        ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin").lower()
        if ext not in MIME:
            raise HTTPException(400, f"Type non supporté: {ext}")
        file_id = uuid.uuid4().hex
        path = f"{APP_NAME}/{user['user_id']}/{file_id}.{ext}"
        data = await file.read()
        limit = MAX_BYTES.get(MIME[ext], DEFAULT_MAX_BYTES)
        if len(data) > limit:
            raise HTTPException(400, f"Fichier trop volumineux (max {limit // (1024*1024)} Mo)")
        result = _put_object(path, data, MIME[ext])
        doc = {
            "file_id": file_id, "user_id": user["user_id"],
            "storage_path": result["path"], "filename": file.filename,
            "content_type": MIME[ext], "size": result.get("size", len(data)),
            "kind": kind, "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.files.insert_one(doc)
        doc.pop("_id", None)
        doc["url"] = f"/api/files/{file_id}"
        return doc

    @api_router.get("/files/{file_id}")
    async def download_file(file_id: str, request: Request,
                            auth: Optional[str] = Query(None),
                            authorization: Optional[str] = Header(None)):
        rec = await db.files.find_one({"file_id": file_id, "is_deleted": False}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Fichier introuvable")
        if rec.get("kind") in ("avatar", "banner", "post", "ad", "deal", "feed"):
            data, ct = _get_object(rec["storage_path"])
            return Response(content=data, media_type=rec.get("content_type", ct))
        student_doc = await db.student_documents.find_one({"file_id": file_id}, {"_id": 0})
        gallery_photo = await db.company_photos.find_one({"file_id": file_id}, {"_id": 0})
        if gallery_photo:
            data, ct = _get_object(rec["storage_path"])
            return Response(content=data, media_type=rec.get("content_type", ct))
        if student_doc:
            owner_id = student_doc["user_id"]
            visibility = student_doc.get("visibility", "after_application")
            if visibility == "public":
                data, ct = _get_object(rec["storage_path"])
                return Response(content=data, media_type=rec.get("content_type", ct))
            try:
                req_user = await get_current_user(request)
            except HTTPException:
                raise HTTPException(401, "Authentification requise pour ce document")
            if req_user["user_id"] == owner_id:
                data, ct = _get_object(rec["storage_path"])
                return Response(content=data, media_type=rec.get("content_type", ct))
            if visibility == "connected":
                has_contact = await db.contacts.find_one({"$or": [
                    {"user_a": owner_id, "user_b": req_user["user_id"]},
                    {"user_a": req_user["user_id"], "user_b": owner_id},
                ]})
                if not has_contact:
                    raise HTTPException(403, "Document réservé aux contacts")
            elif visibility == "after_application":
                ap = await db.applications.find_one(
                    {"candidate_id": owner_id, "company_id": req_user["user_id"]},
                )
                if not ap:
                    raise HTTPException(403, "Document accessible après candidature")
            else:
                raise HTTPException(403, "Document privé")
            data, ct = _get_object(rec["storage_path"])
            return Response(content=data, media_type=rec.get("content_type", ct))
        try:
            req_user = await get_current_user(request)
            if req_user["user_id"] != rec["user_id"]:
                raise HTTPException(403, "Accès refusé")
        except HTTPException:
            raise HTTPException(401, "Authentification requise")
        data, ct = _get_object(rec["storage_path"])
        return Response(content=data, media_type=rec.get("content_type", ct))

    # Expose helpers so legacy code (avatar/banner uploads still in server.py) can reuse them
    register_storage_routes.put_object = _put_object  # type: ignore[attr-defined]
    register_storage_routes.get_object = _get_object  # type: ignore[attr-defined]
    register_storage_routes.init_storage = _init_storage  # type: ignore[attr-defined]
    register_storage_routes.MIME = MIME  # type: ignore[attr-defined]
