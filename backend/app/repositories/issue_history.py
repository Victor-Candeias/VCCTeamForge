from datetime import datetime
from typing import Any

from bson import ObjectId

from app.repositories.base import MongoRepository


class IssueHistoryRepository(MongoRepository):
    """Eventos de alteração das issues (collection separada para evitar arrays ilimitados)."""

    collection_name = "issue_history"

    def record(
        self,
        *,
        issue_id: ObjectId,
        project_id: ObjectId,
        actor_id: ObjectId | None,
        event_type: str,
        now: datetime,
        changes: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.collection.insert_one(
            {
                "issueId": issue_id,
                "projectId": project_id,
                "actorId": actor_id,
                "type": event_type,
                "changes": changes or [],
                "details": details or {},
                "createdAt": now,
            }
        )

    def list_page(self, issue_id: ObjectId, *, skip: int, limit: int) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"issueId": issue_id})
            .sort([("createdAt", -1), ("_id", -1)])
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)

    def count(self, issue_id: ObjectId) -> int:
        return self.collection.count_documents({"issueId": issue_id})
