"""Contacts routes — split from server.py.
Endpoints:
- POST   /api/contacts/request
- POST   /api/contacts/{request_id}/accept
- POST   /api/contacts/{request_id}/refuse
- GET    /api/contacts
- DELETE /api/contacts/request/{request_id}
- DELETE /api/contacts/{contact_user_id}
- POST   /api/contacts/block/{target_id}
- GET    /api/contacts/status/{other_id}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from models import ContactRequestIn  # noqa: F401


def register_contacts_routes(api_router, db, get_current_user, notify):
    @api_router.post("/contacts/request")
    async def request_contact(data: ContactRequestIn, user=Depends(get_current_user)):
        if data.to_user_id == user["user_id"]:
            raise HTTPException(400, "Impossible")
        existing = await db.contact_requests.find_one(
            {"from_id": user["user_id"], "to_id": data.to_user_id, "status": "pending"}
        )
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
        await notify(
            data.to_user_id, "contact_request",
            f"{user['name']} souhaite ajouter en contact",
            "/contacts",
            {"user_id": user["user_id"], "name": user["name"]},
        )
        return {"ok": True, "request_id": rid}

    @api_router.post("/contacts/{request_id}/accept")
    async def accept_contact(request_id: str, user=Depends(get_current_user)):
        req = await db.contact_requests.find_one({"request_id": request_id})
        if not req or req["to_id"] != user["user_id"]:
            raise HTTPException(404, "Introuvable")
        await db.contact_requests.update_one(
            {"request_id": request_id}, {"$set": {"status": "accepted"}}
        )
        pair = sorted([req["from_id"], req["to_id"]])
        await db.contacts.insert_one({
            "contact_id": f"ct_{uuid.uuid4().hex[:10]}",
            "user_a": pair[0],
            "user_b": pair[1],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await notify(
            req["from_id"], "contact_accepted",
            f"{user['name']} a accepté votre demande de contact", "/contacts",
        )
        return {"ok": True}

    @api_router.post("/contacts/{request_id}/refuse")
    async def refuse_contact(request_id: str, user=Depends(get_current_user)):
        req = await db.contact_requests.find_one({"request_id": request_id})
        if not req or req["to_id"] != user["user_id"]:
            raise HTTPException(404, "Introuvable")
        await db.contact_requests.update_one(
            {"request_id": request_id}, {"$set": {"status": "refused"}}
        )
        return {"ok": True}

    @api_router.get("/contacts")
    async def list_contacts(user=Depends(get_current_user)):
        cs = await db.contacts.find(
            {"$or": [{"user_a": user["user_id"]}, {"user_b": user["user_id"]}]},
            {"_id": 0},
        ).to_list(200)
        pending = await db.contact_requests.find(
            {"to_id": user["user_id"], "status": "pending"}, {"_id": 0}
        ).to_list(50)
        sent = await db.contact_requests.find(
            {"from_id": user["user_id"], "status": "pending"}, {"_id": 0}
        ).to_list(50)
        contacts = []
        for c in cs:
            other_id = c["user_b"] if c["user_a"] == user["user_id"] else c["user_a"]
            other = await db.users.find_one({"user_id": other_id}, {"_id": 0, "password": 0})
            if other:
                contacts.append(other)
        return {"contacts": contacts, "pending": pending, "sent": sent}

    # Extensions
    @api_router.delete("/contacts/request/{request_id}")
    async def cancel_contact_request(request_id: str, user=Depends(get_current_user)):
        r = await db.contact_requests.find_one({"request_id": request_id})
        if not r or r["from_id"] != user["user_id"]:
            raise HTTPException(403, "Interdit")
        await db.contact_requests.delete_one({"request_id": request_id})
        return {"ok": True}

    @api_router.delete("/contacts/{contact_user_id}")
    async def remove_contact(contact_user_id: str, user=Depends(get_current_user)):
        await db.contacts.delete_many({"$or": [
            {"user_a": user["user_id"], "user_b": contact_user_id},
            {"user_a": contact_user_id, "user_b": user["user_id"]},
        ]})
        return {"ok": True}

    @api_router.post("/contacts/block/{target_id}")
    async def block_user(target_id: str, user=Depends(get_current_user)):
        existing = await db.blocked_users.find_one(
            {"blocker_id": user["user_id"], "blocked_id": target_id}
        )
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

    @api_router.get("/contacts/status/{other_id}")
    async def contact_status(other_id: str, user=Depends(get_current_user)):
        if other_id == user["user_id"]:
            return {"status": "self"}
        c = await db.contacts.find_one({"$or": [
            {"user_a": user["user_id"], "user_b": other_id},
            {"user_a": other_id, "user_b": user["user_id"]},
        ]})
        if c:
            return {"status": "connected"}
        sent = await db.contact_requests.find_one(
            {"from_id": user["user_id"], "to_id": other_id, "status": "pending"}, {"_id": 0}
        )
        if sent:
            return {"status": "sent", "request_id": sent["request_id"]}
        received = await db.contact_requests.find_one(
            {"from_id": other_id, "to_id": user["user_id"], "status": "pending"}, {"_id": 0}
        )
        if received:
            return {"status": "received", "request_id": received["request_id"]}
        return {"status": "none"}
