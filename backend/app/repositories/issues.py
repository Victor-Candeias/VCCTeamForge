from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.repositories.base import MongoRepository


class IssueRepository(MongoRepository):
    collection_name = "issues"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document["_id"] = self.collection.insert_one(document).inserted_id
        return document

    def find_by_id(self, issue_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": issue_id})

    def find_by_key(self, key: str) -> dict[str, Any] | None:
        return self.collection.find_one({"key": key})

    def find_many_by_ids(self, issue_ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        if not issue_ids:
            return {}
        return {
            document["_id"]: document
            for document in self.collection.find({"_id": {"$in": list(set(issue_ids))}})
        }

    def search(
        self,
        query: dict[str, Any],
        *,
        sort: list[tuple[str, int]],
        skip: int,
        limit: int,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find(query, projection).sort(sort).skip(skip).limit(limit)
        return list(cursor)

    def count(self, query: dict[str, Any]) -> int:
        return self.collection.count_documents(query)

    def distinct_labels(self, project_id: ObjectId) -> list[str]:
        return sorted(self.collection.distinct("labels", {"projectId": project_id}))

    def update_versioned(
        self,
        issue_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Aplica a alteração só se ``version`` coincidir; ``None`` se divergir ou não existir."""
        return self.collection.find_one_and_update(
            {"_id": issue_id, "version": version},
            {"$set": {**set_fields, "updatedAt": now}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )
