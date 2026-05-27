"""Applications routes — split from server.py.
Endpoints:
- POST  /api/applications           — candidate applies to an offer
- GET   /api/applications           — list (candidate's own / company's received / admin's all)
- PATCH /api/applications/{app_id}  — company updates status
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from models import ApplicationIn


def register_applications_routes(api_router, db, get_current_user, notify):
    @api_router.post("/applications")
    async def apply(data: ApplicationIn, user=Depends(get_current_user)):
        if user["role"] != "candidate":
            raise HTTPException(403, "Réservé aux candidats")
        offer = await db.offers.find_one({"offer_id": data.offer_id}, {"_id": 0})
        if not offer:
            raise HTTPException(404, "Offre introuvable")
        existing = await db.applications.find_one(
            {"offer_id": data.offer_id, "candidate_id": user["user_id"]}
        )
        if existing:
            raise HTTPException(400, "Vous avez déjà postulé")
        app_id = f"app_{uuid.uuid4().hex[:12]}"
        online_cv_snapshot = None
        if data.use_online_cv:
            cv_doc = await db.student_cvs.find_one({"user_id": user["user_id"]}, {"_id": 0})
            if cv_doc:
                online_cv_snapshot = cv_doc
        selected_docs = []
        if data.uploaded_doc_ids:
            docs = await db.student_documents.find(
                {"user_id": user["user_id"], "doc_id": {"$in": data.uploaded_doc_ids}},
                {"_id": 0},
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
        await notify(
            offer["company_id"], "application",
            f"{user['name']} a postulé à \"{offer['title']}\"",
            "/applications",
            {"user_id": user["user_id"], "name": user["name"]},
        )
        doc.pop("_id", None)
        return doc

    @api_router.get("/applications")
    async def my_applications(user=Depends(get_current_user)):
        if user["role"] == "candidate":
            apps = await db.applications.find(
                {"candidate_id": user["user_id"]}, {"_id": 0}
            ).sort("created_at", -1).to_list(100)
        elif user["role"] == "company":
            apps = await db.applications.find(
                {"company_id": user["user_id"]}, {"_id": 0}
            ).sort("created_at", -1).to_list(100)
        else:
            apps = await db.applications.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return apps

    @api_router.patch("/applications/{app_id}")
    async def update_application(app_id: str, data: dict, user=Depends(get_current_user)):
        app_doc = await db.applications.find_one({"app_id": app_id}, {"_id": 0})
        if not app_doc:
            raise HTTPException(404, "Introuvable")
        if app_doc["company_id"] != user["user_id"] and user["role"] != "admin":
            raise HTTPException(403, "Interdit")
        status = data.get("status")
        if status in ("vue", "en_attente", "acceptee", "refusee"):
            await db.applications.update_one({"app_id": app_id}, {"$set": {"status": status}})
            await notify(
                app_doc["candidate_id"], "application_status",
                f"Votre candidature \"{app_doc['offer_title']}\" est maintenant: {status}",
                "/dashboard",
            )
        return {"ok": True}
