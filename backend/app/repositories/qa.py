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

    def find_many_by_ids(self, ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        if not ids:
            return {}
        projection = {"name": 1, "status": 1, "projectId": 1, "testCaseIds": 1}
        return {
            document["_id"]: document
            for document in self.collection.find({"_id": {"$in": list(set(ids))}}, projection)
        }

    def names_by_ids(self, ids: list[ObjectId]) -> dict[ObjectId, str]:
        if not ids:
            return {}
        cursor = self.collection.find({"_id": {"$in": list(set(ids))}}, {"name": 1})
        return {document["_id"]: document["name"] for document in cursor}

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


class TestRunRepository(_VersionedRepository):
    __test__ = False
    collection_name = "test_runs"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document["_id"] = self.collection.insert_one(document).inserted_id
        return document

    def update_versioned(
        self,
        test_run_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self._update_versioned(test_run_id, version, now=now, set_fields=set_fields)

    def add_bug(
        self, test_run_id: ObjectId, issue_id: ObjectId, *, now: datetime, max_bugs: int
    ) -> dict[str, Any] | None:
        """Liga o bug à execução (sem ultrapassar ``max_bugs``) e incrementa a versão."""
        return self.collection.find_one_and_update(
            {"_id": test_run_id, f"bugIssueIds.{max_bugs - 1}": {"$exists": False}},
            {
                "$addToSet": {"bugIssueIds": issue_id},
                "$set": {"updatedAt": now},
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )

    def latest_by_case(self, test_plan_id: ObjectId) -> dict[ObjectId, list[dict[str, Any]]]:
        """As duas execuções mais recentes de cada caso no plano (última e anterior)."""
        pipeline = [
            {"$match": {"testPlanId": test_plan_id}},
            {"$sort": {"executedAt": -1, "_id": -1}},
            {
                "$group": {
                    "_id": "$testCaseId",
                    "runs": {
                        "$push": {
                            "_id": "$_id",
                            "result": "$result",
                            "executedAt": "$executedAt",
                            "executedBy": "$executedBy",
                        }
                    },
                }
            },
            {"$project": {"runs": {"$slice": ["$runs", 2]}}},
        ]
        return {row["_id"]: row["runs"] for row in self.collection.aggregate(pipeline)}
