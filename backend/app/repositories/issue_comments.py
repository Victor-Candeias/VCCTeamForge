from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.repositories.base import MongoRepository


class IssueCommentRepository(MongoRepository):
    collection_name = "issue_comments"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document["_id"] = self.collection.insert_one(document).inserted_id
        return document

    def find_for_issue(self, issue_id: ObjectId, comment_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": comment_id, "issueId": issue_id})

    def list_page(self, issue_id: ObjectId, *, skip: int, limit: int) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"issueId": issue_id})
            .sort([("createdAt", 1), ("_id", 1)])
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)

    def count(self, issue_id: ObjectId) -> int:
        return self.collection.count_documents({"issueId": issue_id})

    def update_body(
        self, comment_id: ObjectId, body: str, *, now: datetime
    ) -> dict[str, Any] | None:
        return self.collection.find_one_and_update(
            {"_id": comment_id, "deletedAt": None},
            {"$set": {"body": body, "editedAt": now, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )

    def soft_delete(
        self, comment_id: ObjectId, *, actor_id: ObjectId, now: datetime
    ) -> dict[str, Any] | None:
        """Marca como removido e apaga o texto; ``None`` se já estava removido."""
        return self.collection.find_one_and_update(
            {"_id": comment_id, "deletedAt": None},
            {
                "$set": {"deletedAt": now, "deletedBy": actor_id, "updatedAt": now},
                "$unset": {"body": ""},
            },
            return_document=ReturnDocument.AFTER,
        )
