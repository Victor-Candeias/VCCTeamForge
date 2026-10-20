"""Construção de snapshots de sprint (compromisso, diários e fecho)."""

import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.logging import request_id_var
from app.domain.issues import IssueStatus
from app.domain.sprints import SprintStatus
from app.repositories.issues import IssueRepository
from app.repositories.sprint_snapshots import SprintSnapshotRepository
from app.repositories.sprints import SprintRepository

logger = logging.getLogger(__name__)


class SnapshotKind:
    COMMITMENT = "commitment"
    DAILY = "daily"
    CLOSING = "closing"


SNAPSHOT_PROJECTION = {
    "projectId": 1,
    "sprintId": 1,
    "key": 1,
    "title": 1,
    "type": 1,
    "status": 1,
    "storyPoints": 1,
    "assigneeId": 1,
    "blocked": 1,
}


def snapshot_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issueId": issue["_id"],
        "key": issue["key"],
        "title": issue["title"],
        "type": issue["type"],
        "status": issue["status"],
        "storyPoints": issue.get("storyPoints"),
        "assigneeId": issue.get("assigneeId"),
        "blocked": bool(issue.get("blocked")),
    }


def snapshot_totals(issues: list[dict[str, Any]]) -> dict[str, Any]:
    done = [issue for issue in issues if issue["status"] == IssueStatus.DONE]
    return {
        "issueCount": len(issues),
        "storyPoints": sum(issue.get("storyPoints") or 0 for issue in issues),
        "unestimatedCount": sum(1 for issue in issues if issue.get("storyPoints") is None),
        "completedIssueCount": len(done),
        "completedStoryPoints": sum(issue.get("storyPoints") or 0 for issue in done),
    }


def snapshot_document(
    sprint: dict[str, Any], issues: list[dict[str, Any]], kind: str, now: datetime
) -> dict[str, Any]:
    """``day`` (AAAA-MM-DD, UTC) identifica o snapshot; o diário é substituído ao longo do dia."""
    items = [snapshot_issue(issue) for issue in issues]
    return {
        "sprintId": sprint["_id"],
        "projectId": sprint["projectId"],
        "kind": kind,
        "day": now.date().isoformat(),
        "takenAt": now,
        "issues": items,
        "totals": snapshot_totals(items),
    }


class DailySnapshotRecorder:
    """Snapshot diário do sprint para o burndown (DEV-019).

    É best-effort: uma falha fica no log e não anula a operação que a originou.
    """

    def __init__(self, db: Database) -> None:
        self.sprints = SprintRepository(db)
        self.issues = IssueRepository(db)
        self.snapshots = SprintSnapshotRepository(db)

    def record(
        self,
        sprint_id: ObjectId,
        now: datetime,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        """Sem ``issues`` só regista sprints ativos, lendo as issues atuais."""
        try:
            sprint = self.sprints.find_by_id(sprint_id)
            if sprint is None:
                return
            if issues is None:
                if sprint["status"] != SprintStatus.ACTIVE:
                    return
                issues = self.issues.find_in_sprint(sprint_id, SNAPSHOT_PROJECTION)
            self.snapshots.save(snapshot_document(sprint, issues, SnapshotKind.DAILY, now))
        except PyMongoError:
            logger.exception(
                "Falha ao gravar o snapshot diário do sprint %s (requestId=%s)",
                sprint_id,
                request_id_var.get(),
            )
