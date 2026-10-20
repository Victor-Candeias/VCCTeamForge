"""Ciclo de vida do sprint: início com snapshot do compromisso (DEV-017).

Sem transações (MongoDB 4.4 standalone): a transição de estado é condicional à versão e ao
estado; se o snapshot falhar depois da transição, o sprint volta ao estado anterior.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.errors import BusinessRuleError, ForbiddenError, NotFoundError
from app.core.logging import request_id_var
from app.domain.sprints import SprintRuleError, SprintStatus, can_manage_sprints, validate_startable
from app.domain.users import User
from app.repositories.sprint_snapshots import SprintSnapshotRepository
from app.repositories.sprints import ActiveSprintExistsError
from app.schemas.sprints import (
    AddedIssue,
    CommittedIssue,
    SprintCommitment,
    SprintResponse,
    SprintStart,
)
from app.services.sprint_snapshots import SNAPSHOT_PROJECTION, SnapshotKind, snapshot_document
from app.services.sprints import SprintService, _rule_error

logger = logging.getLogger(__name__)


class SprintLifecycleService(SprintService):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.snapshots = SprintSnapshotRepository(db)

    # Início --------------------------------------------------------------------------------

    def start(self, user: User, sprint_id: ObjectId, data: SprintStart) -> SprintResponse:
        sprint, project = self._get_manageable(user, sprint_id)
        self._check_version(sprint, data.version)
        self._ensure_no_other_active(sprint)

        issues = self.issues.find_in_sprint(sprint_id, SNAPSHOT_PROJECTION)
        now = datetime.now(UTC)
        try:
            validate_startable(sprint["status"], sprint["endDate"].date(), now.date(), len(issues))
        except SprintRuleError as error:
            raise _rule_error(error) from error

        snapshot = snapshot_document(sprint, issues, SnapshotKind.COMMITMENT, now)
        totals = snapshot["totals"]
        try:
            updated = self.sprints.transition(
                sprint_id,
                data.version,
                from_status=SprintStatus.PLANNED,
                now=now,
                set_fields={
                    "status": SprintStatus.ACTIVE.value,
                    "startedAt": now,
                    "startedBy": user.id,
                    "committedIssueCount": totals["issueCount"],
                    "committedStoryPoints": totals["storyPoints"],
                },
            )
        except ActiveSprintExistsError as error:
            raise self._active_exists() from error
        updated = self._require_updated(updated, sprint_id)

        try:
            self.snapshots.save(snapshot)
        except PyMongoError:
            self._revert_start(updated)
            raise

        self._audit(
            "sprint.started",
            user,
            project,
            updated,
            now,
            {
                "committedIssueCount": totals["issueCount"],
                "committedStoryPoints": totals["storyPoints"],
            },
        )
        return self.to_response(user, project, updated)

    # Compromisso ---------------------------------------------------------------------------

    def commitment(self, user: User, sprint_id: ObjectId) -> SprintCommitment:
        sprint, _ = self._get_with_project(user, sprint_id)
        snapshot = (
            self.snapshots.find_latest(sprint_id, SnapshotKind.COMMITMENT)
            if sprint.get("startedAt")
            else None
        )
        if snapshot is None:
            raise NotFoundError("O sprint ainda não foi iniciado")

        current = self._current_issues(sprint)
        committed_ids = {item["issueId"] for item in snapshot["issues"]}
        outside = self.issues.find_many_by_ids(
            [issue_id for issue_id in committed_ids if issue_id not in current]
        )
        committed = []
        for item in snapshot["issues"]:
            now_issue = current.get(item["issueId"]) or outside.get(item["issueId"])
            committed.append(
                CommittedIssue(
                    issue_id=str(item["issueId"]),
                    key=item["key"],
                    title=item["title"],
                    type=item["type"],
                    status=item["status"],
                    story_points=item.get("storyPoints"),
                    current_status=now_issue["status"] if now_issue else None,
                    current_story_points=now_issue.get("storyPoints") if now_issue else None,
                    in_sprint=item["issueId"] in current,
                )
            )
        added = [
            AddedIssue(
                issue_id=str(issue_id),
                key=issue["key"],
                title=issue["title"],
                type=issue["type"],
                status=issue["status"],
                story_points=issue.get("storyPoints"),
            )
            for issue_id, issue in current.items()
            if issue_id not in committed_ids
        ]
        totals = snapshot["totals"]
        return SprintCommitment(
            sprint_id=str(sprint_id),
            taken_at=snapshot["takenAt"],
            issue_count=totals["issueCount"],
            story_points=totals["storyPoints"],
            unestimated_count=totals["unestimatedCount"],
            removed_count=sum(1 for item in committed if not item.in_sprint),
            added_count=len(added),
            added_story_points=sum(item.story_points or 0 for item in added),
            issues=committed,
            added=added,
        )

    # Auxiliares ----------------------------------------------------------------------------

    def _get_manageable(
        self, user: User, sprint_id: ObjectId
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sprint, project = self._get_with_project(user, sprint_id)
        if not can_manage_sprints(user):
            raise ForbiddenError("Sem permissão para gerir sprints")
        self._ensure_writable_project(project)
        return sprint, project

    def _ensure_no_other_active(self, sprint: dict[str, Any]) -> None:
        active = self.sprints.find_active(sprint["projectId"])
        if active is not None and active["_id"] != sprint["_id"]:
            raise self._active_exists(active)

    @staticmethod
    def _active_exists(active: dict[str, Any] | None = None) -> BusinessRuleError:
        extra = {"sprintId": str(active["_id"])} if active else {}
        name = f" ({active['name']})" if active else ""
        return BusinessRuleError(
            f"Já existe um sprint ativo neste projeto{name}", field="status", **extra
        )

    def _current_issues(self, sprint: dict[str, Any]) -> dict[ObjectId, dict[str, Any]]:
        """Issues do sprint: no fecho ficam congeladas no snapshot de fecho."""
        if sprint["status"] == SprintStatus.CLOSED:
            closing = self.snapshots.find_latest(sprint["_id"], SnapshotKind.CLOSING)
            if closing is not None:
                return {
                    item["issueId"]: {**item, "_id": item["issueId"]} for item in closing["issues"]
                }
        issues = self.issues.find_in_sprint(sprint["_id"], SNAPSHOT_PROJECTION)
        return {issue["_id"]: issue for issue in issues}

    def _revert_start(self, sprint: dict[str, Any]) -> None:
        try:
            self.sprints.transition(
                sprint["_id"],
                sprint["version"],
                from_status=SprintStatus.ACTIVE,
                now=datetime.now(UTC),
                set_fields={
                    "status": SprintStatus.PLANNED.value,
                    "startedAt": None,
                    "startedBy": None,
                    "committedIssueCount": None,
                    "committedStoryPoints": None,
                },
            )
        except PyMongoError:
            logger.exception(
                "Falha ao reverter o início do sprint %s (requestId=%s)",
                sprint["_id"],
                request_id_var.get(),
            )
