from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.repositories.base import MongoRepository


class AttachmentRepository(MongoRepository):
    collection_name = "attachments"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document["_id"] = self.collection.insert_one(document).inserted_id
        return document

    def find_active(self, attachment_id: ObjectId) -> dict[str, Any] | None:
        """Anexo de issue ativo (as evidências de execuções não têm ``issueId``)."""
        return self.collection.find_one(
            {"_id": attachment_id, "issueId": {"$ne": None}, "deletedAt": None}
        )

    def list_for_issue(self, issue_id: ObjectId) -> list[dict[str, Any]]:
        cursor = self.collection.find({"issueId": issue_id, "deletedAt": None}).sort(
            [("createdAt", 1), ("_id", 1)]
        )
        return list(cursor)

    def count_for_issue(self, issue_id: ObjectId) -> int:
        return self.collection.count_documents({"issueId": issue_id, "deletedAt": None})

    # Evidências de execuções de teste (DEV-021) ------------------------------------------------

    def find_active_evidence(
        self, attachment_id: ObjectId, test_run_id: ObjectId
    ) -> dict[str, Any] | None:
        return self.collection.find_one(
            {"_id": attachment_id, "testRunId": test_run_id, "deletedAt": None}
        )

    def list_for_test_run(self, test_run_id: ObjectId) -> list[dict[str, Any]]:
        cursor = self.collection.find({"testRunId": test_run_id, "deletedAt": None}).sort(
            [("createdAt", 1), ("_id", 1)]
        )
        return list(cursor)

    def count_for_test_run(self, test_run_id: ObjectId) -> int:
        return self.collection.count_documents({"testRunId": test_run_id, "deletedAt": None})

    def count_by_test_run(self, test_run_ids: list[ObjectId]) -> dict[ObjectId, int]:
        if not test_run_ids:
            return {}
        pipeline = [
            {"$match": {"testRunId": {"$in": test_run_ids}, "deletedAt": None}},
            {"$group": {"_id": "$testRunId", "count": {"$sum": 1}}},
        ]
        return {row["_id"]: row["count"] for row in self.collection.aggregate(pipeline)}

    def soft_delete(
        self, attachment_id: ObjectId, *, actor_id: ObjectId, now: datetime
    ) -> dict[str, Any] | None:
        return self.collection.find_one_and_update(
            {"_id": attachment_id, "deletedAt": None},
            {"$set": {"deletedAt": now, "deletedBy": actor_id, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )

    def active_storage_keys(self) -> set[str]:
        cursor = self.collection.find({"deletedAt": None}, {"storageKey": 1})
        return {document["storageKey"] for document in cursor}
