"""Associação de issues a sprints (DEV-016).

Sem transações (MongoDB 4.4 standalone): cada issue muda de sprint com uma atualização
condicional ao sprint atual, para que pedidos concorrentes não se sobreponham.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.sprints import (
    OPEN_STATUSES,
    SPRINT_ISSUES_MAX,
    SprintRuleError,
    SprintStatus,
    can_manage_sprints,
    validate_plannable,
)
from app.domain.users import User
from app.schemas.sprints import SprintIssuesAdd, SprintResponse
from app.services.common import object_id_or_422
from app.services.issue_history import HistoryEvent, IssueActivityRecorder
from app.services.sprints import SprintService


class SprintPlanningService(SprintService):
    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.activity = IssueActivityRecorder(db)

    def add_issues(self, user: User, sprint_id: ObjectId, data: SprintIssuesAdd) -> SprintResponse:
        sprint, project = self._get_plannable(user, sprint_id)
        issue_ids = list(
            dict.fromkeys(object_id_or_422(value, "issueIds") for value in data.issue_ids)
        )
        issues = self.issues.find_many_by_ids(issue_ids)

        to_move: list[dict[str, Any]] = []
        for issue_id in issue_ids:
            issue = issues.get(issue_id)
            if issue is None or issue["projectId"] != sprint["projectId"]:
                raise BusinessRuleError(
                    "Issue inexistente ou de outro projeto", field="issueIds", issueId=str(issue_id)
                )
            if issue.get("sprintId") == sprint_id:
                continue
            self._validate_plannable(issue)
            self._ensure_source_sprint_open(issue)
            to_move.append(issue)

        if not to_move:
            return self.to_response(user, project, sprint)
        if self.issues.count_in_sprint(sprint_id) + len(to_move) > SPRINT_ISSUES_MAX:
            raise BusinessRuleError(
                f"Um sprint pode ter no máximo {SPRINT_ISSUES_MAX} issues", field="issueIds"
            )

        now = datetime.now(UTC)
        moved: list[str] = []
        for issue in to_move:
            self._move(user, issue, sprint_id, now)
            moved.append(issue["key"])
        self._audit("sprint.issues_added", user, project, sprint, now, {"issueKeys": moved})
        return self.to_response(user, project, sprint)

    def remove_issue(self, user: User, sprint_id: ObjectId, issue_id: ObjectId) -> SprintResponse:
        sprint, project = self._get_plannable(user, sprint_id)
        issue = self.issues.find_by_id(issue_id)
        if issue is None or issue.get("sprintId") != sprint_id:
            raise NotFoundError("A issue não pertence a este sprint")
        now = datetime.now(UTC)
        self._move(user, issue, None, now)
        self._audit("sprint.issue_removed", user, project, sprint, now, {"issueKey": issue["key"]})
        return self.to_response(user, project, sprint)

    # Auxiliares ----------------------------------------------------------------------------

    def _get_plannable(
        self, user: User, sprint_id: ObjectId
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sprint, project = self._get_with_project(user, sprint_id)
        if not can_manage_sprints(user):
            raise ForbiddenError("Sem permissão para planear sprints")
        self._ensure_writable_project(project)
        if sprint["status"] not in OPEN_STATUSES:
            raise BusinessRuleError("Um sprint fechado não pode ser alterado", field="status")
        return sprint, project

    @staticmethod
    def _validate_plannable(issue: dict[str, Any]) -> None:
        try:
            validate_plannable(issue["type"], issue["status"])
        except SprintRuleError as error:
            raise BusinessRuleError(
                f"{issue['key']}: {error}", field=error.field, issueId=str(issue["_id"])
            ) from error

    def _ensure_source_sprint_open(self, issue: dict[str, Any]) -> None:
        source_id = issue.get("sprintId")
        if source_id is None:
            return
        source = self.sprints.find_by_id(source_id)
        if source is not None and source["status"] == SprintStatus.CLOSED:
            raise BusinessRuleError(
                f"{issue['key']} pertence a um sprint fechado",
                field="issueIds",
                issueId=str(issue["_id"]),
            )

    def _move(
        self, user: User, issue: dict[str, Any], target: ObjectId | None, now: datetime
    ) -> dict[str, Any]:
        source = issue.get("sprintId")
        updated = self.issues.set_sprint(
            issue["_id"], expected_sprint_id=source, sprint_id=target, now=now
        )
        if updated is None:
            raise ConflictError(
                f"A issue {issue['key']} foi alterada entretanto. Recarregue e tente novamente.",
                issueId=str(issue["_id"]),
            )
        self.activity.record(
            user,
            updated,
            HistoryEvent.UPDATED,
            now=now,
            changes=[
                {
                    "field": "sprintId",
                    "from": str(source) if source else None,
                    "to": str(target) if target else None,
                }
            ],
        )
        return updated
