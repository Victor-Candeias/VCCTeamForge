"""Tentativas de login para rate limiting (removidas automaticamente pelo índice TTL)."""

from datetime import datetime

from app.repositories.base import MongoRepository


class LoginAttemptRepository(MongoRepository):
    collection_name = "login_attempts"

    def record_failure(self, keys: list[str], now: datetime) -> None:
        self.collection.insert_many([{"key": key, "createdAt": now} for key in keys])

    def failures_since(self, key: str, since: datetime) -> list[datetime]:
        cursor = self.collection.find(
            {"key": key, "createdAt": {"$gte": since}}, {"createdAt": 1, "_id": 0}
        ).sort("createdAt", 1)
        return [document["createdAt"] for document in cursor]

    def clear(self, key: str) -> None:
        self.collection.delete_many({"key": key})
