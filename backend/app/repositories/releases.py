from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.domain.releases import HISTORY_MAX
from app.repositories.base import MongoRepository


class ReleaseNameExistsError(Exception):
    pass


class ReleaseRepository(MongoRepository):
    collection_name = "releases"

    def find_by_id(self, release_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": release_id})

    def search(
        self,
        query: dict[str, Any],
        *,
        sort: list[tuple[str, int]],
        skip: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        projection = {"history": 0, "notes": 0, "description": 0}
        cursor = self.collection.find(query, projection)
        return list(cursor.sort(sort).skip(skip).limit(limit))

    def count(self, query: dict[str, Any]) -> int:
        return self.collection.count_documents(query)

    def latest_for_project(self, project_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one(
            {"projectId": project_id}, {"checklist": 1}, sort=[("createdAt", -1)]
        )

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            document["_id"] = self.collection.insert_one(document).inserted_id
        except DuplicateKeyError as error:
            raise ReleaseNameExistsError(document.get("name")) from error
        return document

    def update_versioned(
        self,
        release_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
        history: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Aplica a alteração só se ``version`` coincidir e acrescenta a entrada ao histórico."""
        update: dict[str, Any] = {
            "$set": {**set_fields, "updatedAt": now},
            "$inc": {"version": 1},
        }
        if history is not None:
            update["$push"] = {"history": {"$each": [history], "$slice": -HISTORY_MAX}}
        try:
            return self.collection.find_one_and_update(
                {"_id": release_id, "version": version},
                update,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as error:
            raise ReleaseNameExistsError(set_fields.get("name")) from error
