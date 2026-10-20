"""Relatório/dashboard de sprint: KPIs, burndown, distribuição, bloqueios e velocidade (DEV-019).

O burndown usa os totais dos snapshots (compromisso, diários e fecho): para cada dia vale o
último snapshot até esse dia; num sprint ativo o dia atual usa as issues atuais.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError
from app.domain.issues import IssueStatus
from app.domain.sprints import SprintStatus, duration_days
from app.domain.users import User
from app.repositories.sprint_snapshots import SprintSnapshotRepository
from app.schemas.reports import (
    BlockedIssue,
    BurndownPoint,
    SprintReport,
    SprintReportKpis,
    StatusBreakdown,
    VelocityEntry,
)
from app.services.sprint_snapshots import SnapshotKind, snapshot_totals
from app.services.sprints import SprintService

VELOCITY_SPRINTS = 5

_ISSUE_PROJECTION = {
    "key": 1,
    "title": 1,
    "status": 1,
    "storyPoints": 1,
    "blocked": 1,
    "blockReason": 1,
    "blockedAt": 1,
}


def _points(value: float) -> float:
    return round(value, 2)


def _percent(part: float, whole: float) -> float | None:
    return round(part / whole * 100, 1) if whole > 0 else None


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def ideal_remaining(day: date, start: date, end: date, committed: float) -> float:
    """Linha ideal: compromisso no início a 0 no fim."""
    if day >= end:
        return 0.0
    if day <= start:
        return _points(committed)
    return _points(committed * (end - day).days / (end - start).days)


class SprintReportService(SprintService):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.snapshots = SprintSnapshotRepository(db)

    def report(self, user: User, sprint_id: ObjectId) -> SprintReport:
        sprint, _ = self._get_with_project(user, sprint_id)
        if sprint["status"] == SprintStatus.PLANNED or not sprint.get("startedAt"):
            raise BusinessRuleError("O sprint ainda não foi iniciado", field="status")

        closed = sprint["status"] == SprintStatus.CLOSED
        as_of = sprint["closedAt"] if closed and sprint.get("closedAt") else datetime.now(UTC)
        issues = self._current_issues(sprint, closed)
        totals = snapshot_totals(issues)
        start, end = sprint["startDate"].date(), sprint["endDate"].date()

        return SprintReport(
            sprint_id=str(sprint_id),
            name=sprint["name"],
            goal=sprint.get("goal", ""),
            status=sprint["status"],
            start_date=start,
            end_date=end,
            as_of=as_of,
            kpis=self._kpis(sprint, issues, totals, as_of.date()),
            burndown=self._burndown(sprint, totals, as_of.date(), live=not closed),
            status_breakdown=self._status_breakdown(issues),
            blocked_issues=[
                BlockedIssue(
                    issue_id=str(issue["issueId"]),
                    key=issue["key"],
                    title=issue["title"],
                    status=issue["status"],
                    block_reason=issue.get("blockReason"),
                    blocked_at=issue.get("blockedAt"),
                )
                for issue in issues
                if issue.get("blocked")
            ],
            **self._velocity(sprint),
        )

    # Dados ---------------------------------------------------------------------------------

    def _current_issues(self, sprint: dict[str, Any], closed: bool) -> list[dict[str, Any]]:
        """Itens no formato dos snapshots; um sprint fechado usa o snapshot de fecho."""
        if closed:
            snapshot = self.snapshots.find_latest(sprint["_id"], SnapshotKind.CLOSING)
            if snapshot is not None:
                return snapshot["issues"]
        return [
            {
                "issueId": issue["_id"],
                "key": issue["key"],
                "title": issue["title"],
                "status": issue["status"],
                "storyPoints": issue.get("storyPoints"),
                "blocked": bool(issue.get("blocked")),
                "blockReason": issue.get("blockReason"),
                "blockedAt": issue.get("blockedAt"),
            }
            for issue in self.issues.find_in_sprint(sprint["_id"], _ISSUE_PROJECTION)
        ]

    def _kpis(
        self,
        sprint: dict[str, Any],
        issues: list[dict[str, Any]],
        totals: dict[str, Any],
        today: date,
    ) -> SprintReportKpis:
        commitment = self.snapshots.find_latest(sprint["_id"], SnapshotKind.COMMITMENT)
        committed_ids = {item["issueId"] for item in commitment["issues"]} if commitment else set()
        current_ids = {issue["issueId"] for issue in issues}
        start, end = sprint["startDate"].date(), sprint["endDate"].date()
        total_days = duration_days(start, end)
        elapsed = min(max((today - start).days + 1, 0), total_days)
        return SprintReportKpis(
            committed_issue_count=sprint.get("committedIssueCount") or 0,
            committed_story_points=sprint.get("committedStoryPoints") or 0,
            issue_count=totals["issueCount"],
            story_points=_points(totals["storyPoints"]),
            unestimated_count=totals["unestimatedCount"],
            completed_issue_count=totals["completedIssueCount"],
            completed_story_points=_points(totals["completedStoryPoints"]),
            remaining_story_points=_points(totals["storyPoints"] - totals["completedStoryPoints"]),
            progress_percent=_percent(totals["completedStoryPoints"], totals["storyPoints"]),
            total_days=total_days,
            elapsed_days=elapsed,
            remaining_days=total_days - elapsed,
            blocked_count=sum(1 for issue in issues if issue.get("blocked")),
            added_count=len(current_ids - committed_ids) if commitment else 0,
            removed_count=len(committed_ids - current_ids),
        )

    def _burndown(
        self, sprint: dict[str, Any], current: dict[str, Any], today: date, *, live: bool
    ) -> list[BurndownPoint]:
        start, end = sprint["startDate"].date(), sprint["endDate"].date()
        committed = sprint.get("committedStoryPoints") or 0
        by_day: dict[str, dict[str, Any]] = {}
        # Ordenados por dia e hora: o último snapshot de cada dia prevalece.
        for snapshot in self.snapshots.find_totals(
            sprint["_id"], [SnapshotKind.COMMITMENT, SnapshotKind.DAILY, SnapshotKind.CLOSING]
        ):
            by_day[snapshot["day"]] = snapshot["totals"]
        if live:
            by_day[today.isoformat()] = current

        first = min(start, sprint["startedAt"].date())
        last = max(end, today)
        points: list[BurndownPoint] = []
        latest: dict[str, Any] | None = None
        for day in _days(first, last):
            latest = by_day.get(day.isoformat(), latest)
            known = latest is not None and day <= today
            points.append(
                BurndownPoint(
                    day=day,
                    ideal=ideal_remaining(day, start, end, committed),
                    remaining=(
                        _points(latest["storyPoints"] - latest["completedStoryPoints"])
                        if known and latest
                        else None
                    ),
                    scope=_points(latest["storyPoints"]) if known and latest else None,
                )
            )
        return points

    @staticmethod
    def _status_breakdown(issues: list[dict[str, Any]]) -> list[StatusBreakdown]:
        return [
            StatusBreakdown(
                status=status,
                issue_count=sum(1 for issue in issues if issue["status"] == status),
                story_points=_points(
                    sum(
                        issue.get("storyPoints") or 0
                        for issue in issues
                        if issue["status"] == status
                    )
                ),
            )
            for status in IssueStatus
        ]

    def _velocity(self, sprint: dict[str, Any]) -> dict[str, Any]:
        """Últimos sprints fechados do projeto com início até ao deste sprint (inclusive)."""
        closed = self.sprints.search(
            {
                "projectId": sprint["projectId"],
                "status": SprintStatus.CLOSED.value,
                "startDate": {"$lte": sprint["startDate"]},
            },
            sort=[("startDate", -1)],
            skip=0,
            limit=VELOCITY_SPRINTS,
        )
        entries = []
        for item in reversed(closed):
            result = item.get("result") or {}
            committed = item.get("committedStoryPoints") or 0
            committed_completed = result.get("committedCompletedStoryPoints") or 0
            entries.append(
                VelocityEntry(
                    sprint_id=str(item["_id"]),
                    name=item["name"],
                    committed_story_points=_points(committed),
                    completed_story_points=_points(result.get("completedStoryPoints") or 0),
                    committed_completed_story_points=_points(committed_completed),
                    predictability_percent=_percent(committed_completed, committed),
                )
            )
        average = (
            _points(sum(entry.completed_story_points for entry in entries) / len(entries))
            if entries
            else None
        )
        return {"velocity": entries, "average_velocity": average}
