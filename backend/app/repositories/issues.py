from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument, UpdateOne

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

    # Sprints -------------------------------------------------------------------------------

    def sprint_totals(self, sprint_ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        """Totais de âmbito por sprint (issues, story points, sem estimativa e concluídas)."""
        if not sprint_ids:
            return {}
        done = {"$eq": ["$status", "done"]}
        points = {"$ifNull": ["$storyPoints", 0]}
        pipeline = [
            {"$match": {"sprintId": {"$in": list(set(sprint_ids))}}},
            {
                "$group": {
                    "_id": "$sprintId",
                    "issueCount": {"$sum": 1},
                    "storyPoints": {"$sum": points},
                    "unestimatedCount": {
                        "$sum": {"$cond": [{"$eq": [{"$ifNull": ["$storyPoints", -1]}, -1]}, 1, 0]}
                    },
                    "completedIssueCount": {"$sum": {"$cond": [done, 1, 0]}},
                    "completedStoryPoints": {"$sum": {"$cond": [done, points, 0]}},
                }
            },
        ]
        return {row.pop("_id"): row for row in self.collection.aggregate(pipeline)}

    def count_in_sprint(self, sprint_id: ObjectId) -> int:
        return self.collection.count_documents({"sprintId": sprint_id})

    def set_sprint(
        self,
        issue_id: ObjectId,
        *,
        expected_sprint_id: ObjectId | None,
        sprint_id: ObjectId | None,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Muda o sprint só se a issue ainda estiver em ``expected_sprint_id``.

        Devolve a issue atualizada ou ``None`` se entretanto mudou de sprint.
        """
        return self.collection.find_one_and_update(
            {"_id": issue_id, "sprintId": expected_sprint_id},
            {"$set": {"sprintId": sprint_id, "updatedAt": now}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )

    # Ordem manual (rank) -------------------------------------------------------------------

    def max_rank(self, project_id: ObjectId) -> float:
        document = self.collection.find_one(
            {"projectId": project_id, "rank": {"$ne": None}},
            {"rank": 1},
            sort=[("rank", DESCENDING), ("_id", DESCENDING)],
        )
        return float(document["rank"]) if document else 0.0

    def neighbour(
        self, issue: dict[str, Any], *, below: bool, exclude_id: ObjectId
    ) -> dict[str, Any] | None:
        """Issue imediatamente acima (``below=False``) ou abaixo na ordem ``(rank, _id)``."""
        op, direction = ("$gt", ASCENDING) if below else ("$lt", DESCENDING)
        query = {
            "projectId": issue["projectId"],
            "_id": {"$ne": exclude_id},
            "$or": [
                {"rank": {op: issue["rank"]}},
                {"rank": issue["rank"], "_id": {op: issue["_id"]}},
            ],
        }
        return self.collection.find_one(
            query, {"rank": 1}, sort=[("rank", direction), ("_id", direction)]
        )

    def renormalize_ranks(self, project_id: ObjectId, step: float) -> None:
        """Volta a espaçar os ranks do projeto (mantendo a ordem atual)."""
        cursor = self.collection.find({"projectId": project_id}, {"_id": 1}).sort(
            [("rank", ASCENDING), ("_id", ASCENDING)]
        )
        operations = [
            UpdateOne({"_id": document["_id"]}, {"$set": {"rank": (index + 1) * step}})
            for index, document in enumerate(cursor)
        ]
        if operations:
            self.collection.bulk_write(operations, ordered=False)
