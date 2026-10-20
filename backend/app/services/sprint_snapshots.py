"""Construção de snapshots de sprint (compromisso, diários e fecho)."""

from datetime import datetime
from typing import Any

from app.domain.issues import IssueStatus


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
