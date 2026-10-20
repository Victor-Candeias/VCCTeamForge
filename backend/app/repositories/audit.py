from datetime import datetime
from typing import Any

from bson import ObjectId

from app.core.logging import request_id_var
from app.repositories.base import MongoRepository


class AuditLogRepository(MongoRepository):
    """Registo de eventos críticos. Nunca é apagado (README §5.6)."""

    collection_name = "audit_logs"

    def record(
        self,
        action: str,
        *,
        now: datetime,
        actor_id: ObjectId | None = None,
        entity_type: str | None = None,
        entity_id: Any = None,
        ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.collection.insert_one(
            {
                "action": action,
                "actorId": actor_id,
                "entityType": entity_type,
                "entityId": entity_id,
                "ip": ip,
                "requestId": request_id_var.get(),
                "details": details or {},
                "createdAt": now,
            }
        )

    def search(self, query: dict[str, Any], *, skip: int, limit: int) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find(query)
            .sort([("createdAt", -1), ("_id", -1)])
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)

    def count(self, query: dict[str, Any]) -> int:
        return self.collection.count_documents(query)
