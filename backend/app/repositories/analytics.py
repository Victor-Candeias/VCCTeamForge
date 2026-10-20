"""Consultas de leitura agregadas para o dashboard e as métricas (DEV-023)."""

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.domain.issues import IssueStatus
from app.repositories.base import MongoRepository


class AnalyticsRepository:
    def __init__(self, db: Database) -> None:
        self.issues = db["issues"]
        self.history = db["issue_history"]
        self.test_runs = db["test_runs"]

    def status_breakdown(self, query: dict[str, Any]) -> dict[str, dict[str, float]]:
        """``{status: {count, storyPoints, blocked}}`` das issues que satisfazem ``query``."""
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "storyPoints": {"$sum": {"$ifNull": ["$storyPoints", 0]}},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$blocked", True]}, 1, 0]}},
                }
            },
        ]
        return {
            row["_id"]: {
                "count": row["count"],
                "storyPoints": float(row["storyPoints"]),
                "blocked": row["blocked"],
            }
            for row in self.issues.aggregate(pipeline)
        }

    def count_issues(self, query: dict[str, Any]) -> int:
        return self.issues.count_documents(query)

    def find_issues(
        self,
        query: dict[str, Any],
        *,
        projection: dict[str, int],
        sort: list[tuple[str, int]] | None = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        cursor = self.issues.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def work_started(self, issue_ids: list[ObjectId]) -> dict[ObjectId, datetime]:
        """Primeira passagem de cada issue a ``in_progress`` (histórico de estado)."""
        if not issue_ids:
            return {}
        pipeline = [
            {
                "$match": {
                    "issueId": {"$in": issue_ids},
                    "changes": {
                        "$elemMatch": {"field": "status", "to": IssueStatus.IN_PROGRESS.value}
                    },
                }
            },
            {"$group": {"_id": "$issueId", "startedAt": {"$min": "$createdAt"}}},
        ]
        return {row["_id"]: row["startedAt"] for row in self.history.aggregate(pipeline)}

    def test_run_counts(
        self, project_ids: list[ObjectId], since: datetime, until: datetime | None = None
    ) -> dict[str, int]:
        executed_at: dict[str, Any] = {"$gte": since}
        if until is not None:
            executed_at["$lt"] = until
        pipeline = [
            {"$match": {"projectId": {"$in": project_ids}, "executedAt": executed_at}},
            {"$group": {"_id": "$result", "count": {"$sum": 1}}},
        ]
        return {row["_id"]: row["count"] for row in self.test_runs.aggregate(pipeline)}


class ReportSnapshotRepository(MongoRepository):
    """Agregados diários por projeto para tendências e relatórios históricos."""

    collection_name = "report_snapshots"

    def save(self, document: dict[str, Any]) -> None:
        key = {"projectId": document["projectId"], "day": document["day"]}
        self.collection.replace_one(key, document, upsert=True)

    def find_range(
        self, project_id: ObjectId, first: datetime, last: datetime
    ) -> list[dict[str, Any]]:
        return list(
            self.collection.find(
                {"projectId": project_id, "day": {"$gte": first, "$lte": last}}
            ).sort("day", 1)
        )

    def daily_totals(self, project_ids: list[ObjectId], first: datetime) -> list[dict[str, Any]]:
        """Soma dos KPIs de vários projetos por dia (tendência do dashboard)."""
        if not project_ids:
            return []
        pipeline = [
            {"$match": {"projectId": {"$in": project_ids}, "day": {"$gte": first}}},
            {
                "$group": {
                    "_id": "$day",
                    "openCount": {"$sum": "$kpis.openCount"},
                    "inProgressCount": {"$sum": "$kpis.inProgressCount"},
                    "blockedCount": {"$sum": "$kpis.blockedCount"},
                    "doneCount": {"$sum": "$kpis.doneCount"},
                    "criticalBugCount": {"$sum": "$kpis.criticalBugCount"},
                    "openStoryPoints": {"$sum": "$kpis.openStoryPoints"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return list(self.collection.aggregate(pipeline))
