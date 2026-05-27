"""Messages routes — split from server.py.
Endpoints:
- POST /api/messages         — send message (no realtime push)
- GET  /api/conversations    — list user conversations
- GET  /api/messages/{other_user_id} — fetch conversation messages (marks as read)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel  # noqa: F401

from models import MessageIn  # noqa: F401 — shared model


def register_messages_routes(api_router, db, get_current_user, notify):
    @api_router.post("/messages")
    async def send_message(data: MessageIn, user=Depends(get_current_user)):
        other = await db.users.find_one({"user_id": data.to_user_id}, {"_id": 0})
        if not other:
            raise HTTPException(404, "Destinataire introuvable")
        pair = sorted([user["user_id"], data.to_user_id])
        conv_id = f"conv_{pair[0][-6:]}_{pair[1][-6:]}"
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        attachments = [a.model_dump() for a in (data.attachments or [])]
        if data.attachment and not attachments:
            attachments = [{"type": "file", "url": data.attachment, "file_id": None,
                            "filename": None, "mime": None, "size": None}]
        doc = {
            "message_id": msg_id, "conv_id": conv_id,
            "from_id": user["user_id"], "from_name": user["name"],
            "to_id": data.to_user_id, "to_name": other["name"],
            "content": data.content,
            "attachment": data.attachment,
            "attachments": attachments,
            "read": False,
            "created_at": now,
        }
        await db.messages.insert_one(doc)
        await db.conversations.update_one(
            {"conv_id": conv_id},
            {"$set": {
                "conv_id": conv_id,
                "participants": pair,
                "last_message": data.content or ("📎 " + (attachments[0]["filename"] or "Pièce jointe") if attachments else ""),
                "last_at": now,
            }},
            upsert=True,
        )
        await notify(data.to_user_id, "message",
                     f"Nouveau message de {user['name']}", "/messages",
                     {"user_id": user["user_id"], "name": user["name"]})
        doc.pop("_id", None)
        return doc

    @api_router.get("/conversations")
    async def list_conversations(user=Depends(get_current_user)):
        convs = await db.conversations.find(
            {"participants": user["user_id"]}, {"_id": 0}
        ).sort("last_at", -1).to_list(100)
        result = []
        for c in convs:
            other_id = next((p for p in c["participants"] if p != user["user_id"]), None)
            if not other_id:
                continue
            other = await db.users.find_one({"user_id": other_id}, {"_id": 0, "password": 0})
            unread = await db.messages.count_documents(
                {"conv_id": c["conv_id"], "to_id": user["user_id"], "read": False}
            )
            result.append({**c, "other": other, "unread": unread})
        return result

    @api_router.get("/messages/{other_user_id}")
    async def get_messages(other_user_id: str, user=Depends(get_current_user)):
        pair = sorted([user["user_id"], other_user_id])
        conv_id = f"conv_{pair[0][-6:]}_{pair[1][-6:]}"
        msgs = await db.messages.find({"conv_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        await db.messages.update_many(
            {"conv_id": conv_id, "to_id": user["user_id"]},
            {"$set": {"read": True}},
        )
        return msgs
