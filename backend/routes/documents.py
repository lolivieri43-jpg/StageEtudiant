"""Student documents routes — split from server.py.

Endpoints:
- POST /api/me/documents               — register a doc (file_id) under student's profile
- GET  /api/users/{user_id}/documents  — list documents (with visibility ACL)
- DELETE /api/me/documents/{doc_id}    — remove a doc (owner only)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException


def register_documents_routes(api_router, db, get_current_user, get_optional_user):
    @api_router.post("/me/documents")
    async def add_doc(body: dict, user=Depends(get_current_user)):
        if user["role"] != "candidate":
            raise HTTPException(403, "Étudiants uniquement")
        doc_id = f"d_{uuid.uuid4().hex[:10]}"
        entry = {
            "doc_id": doc_id, "user_id": user["user_id"],
            "file_id": body.get("file_id"),
            "filename": body.get("filename", "document"),
            "doc_type": body.get("doc_type", "cv"),
            "visibility": body.get("visibility", "after_application"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.student_documents.insert_one(entry)
        entry.pop("_id", None)
        return entry

    @api_router.get("/users/{user_id}/documents")
    async def list_user_documents(user_id: str, requester=Depends(get_optional_user)):
        docs = await db.student_documents.find({"user_id": user_id}, {"_id": 0}).to_list(50)
        if requester and requester["user_id"] == user_id:
            return docs
        out = []
        has_contact = False
        has_app = False
        if requester:
            ct = await db.contacts.find_one({"$or": [
                {"user_a": user_id, "user_b": requester["user_id"]},
                {"user_a": requester["user_id"], "user_b": user_id},
            ]})
            has_contact = bool(ct)
            ap = await db.applications.find_one(
                {"candidate_id": user_id, "company_id": requester["user_id"]},
            )
            has_app = bool(ap)
        for d in docs:
            v = d.get("visibility", "after_application")
            ok = (v == "public"
                  or (v == "connected" and has_contact)
                  or (v == "after_application" and has_app))
            if ok:
                out.append(d)
        return out

    @api_router.delete("/me/documents/{doc_id}")
    async def delete_doc(doc_id: str, user=Depends(get_current_user)):
        await db.student_documents.delete_one({"doc_id": doc_id, "user_id": user["user_id"]})
        return {"ok": True}
