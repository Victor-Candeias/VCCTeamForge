from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.repositories.base import MongoRepository


class TestPlanNameExistsError(Exception):
    __test__ = False


class _VersionedRepository(MongoRepository):
    def find_by_id(self, document_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": document_id})

    def search(
        self,
        query: dict[str, Any],
        *,
        sort: list[tuple[str, int]],
        skip: int,
        limit: int,
        projection: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find(query, projection)
        return list(cursor.sort(sort).skip(skip).limit(limit))

    def count(self, query: dict[str, Any]) -> int:
        return self.collection.count_documents(query)

    def _update_versioned(
        self,
        document_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Aplica a alteração só se ``version`` coincidir (controlo otimista)."""
        return self.collection.find_one_and_update(
            {"_id": document_id, "version": version},
            {"$set": {**set_fields, "updatedAt": now}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )


class TestCaseRepository(_VersionedRepository):
    __test__ = False
    collection_name = "test_cases"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document["_id"] = self.collection.insert_one(document).inserted_id
        return document

    def find_many_by_ids(self, ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        if not ids:
            return {}
        projection = {"number": 1, "title": 1, "status": 1, "priority": 1, "projectId": 1}
        return {
            document["_id"]: document
            for document in self.collection.find({"_id": {"$in": list(set(ids))}}, projection)
        }

    def update_versioned(
        self,
        test_case_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self._update_versioned(test_case_id, version, now=now, set_fields=set_fields)


class TestPlanRepository(_VersionedRepository):
    __test__ = False
    collection_name = "test_plans"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            document["_id"] = self.collection.insert_one(document).inserted_id
        except DuplicateKeyError as error:
            raise TestPlanNameExistsError(document.get("name")) from error
        return document

    def update_versioned(
        self,
        test_plan_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            return self._update_versioned(test_plan_id, version, now=now, set_fields=set_fields)
        except DuplicateKeyError as error:
            raise TestPlanNameExistsError(set_fields.get("name")) from error
