"""Sessões no servidor: o cookie contém um token opaco; só o seu SHA-256 é guardado."""

from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId

from app.repositories.base import MongoRepository


class SessionRepository(MongoRepository):
    collection_name = "sessions"

    def create(
        self,
        *,
        user_id: ObjectId,
        token_hash: str,
        csrf_token_hash: str,
        now: datetime,
        idle_timeout: timedelta,
        absolute_timeout: timedelta,
        ip: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        absolute_expires_at = now + absolute_timeout
        document = {
            "tokenHash": token_hash,
            "csrfTokenHash": csrf_token_hash,
            "userId": user_id,
            "createdAt": now,
            "lastSeenAt": now,
            "absoluteExpiresAt": absolute_expires_at,
            # Índice TTL: o MongoDB remove a sessão depois desta data.
            "expiresAt": min(now + idle_timeout, absolute_expires_at),
            "ip": ip,
            "userAgent": (user_agent or "")[:256] or None,
        }
        document["_id"] = self.collection.insert_one(document).inserted_id
        return document

    def find_active(self, token_hash: str, now: datetime) -> dict[str, Any] | None:
        # O monitor TTL corre a cada ~60 s; a validade é sempre verificada aqui.
        return self.collection.find_one({"tokenHash": token_hash, "expiresAt": {"$gt": now}})

    def extend(self, session: dict[str, Any], now: datetime, idle_timeout: timedelta) -> None:
        expires_at = min(now + idle_timeout, session["absoluteExpiresAt"])
        self.collection.update_one(
            {"_id": session["_id"]}, {"$set": {"lastSeenAt": now, "expiresAt": expires_at}}
        )

    def delete(self, session_id: ObjectId) -> None:
        self.collection.delete_one({"_id": session_id})

    def delete_for_user(
        self, user_id: ObjectId, *, except_session_id: ObjectId | None = None
    ) -> int:
        query: dict[str, Any] = {"userId": user_id}
        if except_session_id is not None:
            query["_id"] = {"$ne": except_session_id}
        return self.collection.delete_many(query).deleted_count
