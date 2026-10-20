"""Parâmetros de pesquisa de issues (``GET /api/issues``)."""

from dataclasses import dataclass, field
from typing import Literal

from bson import ObjectId
from fastapi import Query

from app.core.errors import BusinessRuleError, NotFoundError
from app.domain.common import Priority
from app.domain.issues import IssueRuleError, IssueStatus, IssueType, normalize_labels
from app.schemas.common import parse_sort

ISSUE_SORT_FIELDS = {
    "number": "number",
    "priority": "priorityRank",
    "status": "statusRank",
    "updatedAt": "updatedAt",
    "createdAt": "createdAt",
    "title": "title",
    "dueDate": "dueDate",
    "rank": "rank",
}
DEFAULT_ISSUE_SORT = "-number"
SEARCH_TEXT_MAX_LENGTH = 100
MAX_ASSIGNEE_FILTERS = 50

# Responsável: utilizador concreto, o próprio (``me``) ou sem responsável (``none``).
AssigneeFilter = ObjectId | Literal["me", "none"]


def _object_id(value: str, field_name: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise BusinessRuleError("Identificador inválido", field=field_name)
    return ObjectId(value)


def _project_object_id(value: str) -> ObjectId:
    # Como nas rotas: um projeto com ID mal formado é tratado como inexistente.
    if not ObjectId.is_valid(value):
        raise NotFoundError("Projeto não encontrado")
    return ObjectId(value)


@dataclass
class IssueSearchQuery:
    project_id: ObjectId | None = None
    statuses: list[IssueStatus] = field(default_factory=list)
    priorities: list[Priority] = field(default_factory=list)
    types: list[IssueType] = field(default_factory=list)
    assignees: list[AssigneeFilter] = field(default_factory=list)
    sprint_id: ObjectId | Literal["none"] | None = None
    labels: list[str] = field(default_factory=list)
    blocked: bool | None = None
    parent_issue_id: ObjectId | None = None
    text: str | None = None
    sort: list[tuple[str, int]] = field(
        default_factory=lambda: parse_sort(None, ISSUE_SORT_FIELDS, DEFAULT_ISSUE_SORT)
    )

    @classmethod
    def from_query(
        cls,
        project_id: str | None = Query(default=None, alias="projectId"),
        statuses: list[IssueStatus] = Query(default_factory=list, alias="status"),
        priorities: list[Priority] = Query(default_factory=list, alias="priority"),
        types: list[IssueType] = Query(default_factory=list, alias="type"),
        assignees: list[str] = Query(default_factory=list, alias="assigneeId"),
        sprint_id: str | None = Query(default=None, alias="sprintId"),
        labels: list[str] = Query(default_factory=list, alias="label"),
        blocked: bool | None = Query(default=None),
        parent_issue_id: str | None = Query(default=None, alias="parentIssueId"),
        q: str | None = Query(default=None, max_length=SEARCH_TEXT_MAX_LENGTH),
        sort: str | None = Query(default=None, max_length=30),
    ) -> "IssueSearchQuery":
        """Dependência FastAPI: valida e converte os parâmetros de query (inválido → 422)."""
        if len(assignees) > MAX_ASSIGNEE_FILTERS:
            raise BusinessRuleError(
                f"No máximo {MAX_ASSIGNEE_FILTERS} responsáveis", field="assigneeId"
            )
        parsed_assignees: list[AssigneeFilter] = [
            value if value in ("me", "none") else _object_id(value, "assigneeId")
            for value in (item.strip() for item in assignees)
        ]
        try:
            normalized_labels = normalize_labels(labels)
        except IssueRuleError as error:
            raise BusinessRuleError(str(error), field="label") from error
        return cls(
            project_id=_project_object_id(project_id) if project_id else None,
            statuses=list(dict.fromkeys(statuses)),
            priorities=list(dict.fromkeys(priorities)),
            types=list(dict.fromkeys(types)),
            assignees=parsed_assignees,
            sprint_id=(
                None
                if not sprint_id
                else "none"
                if sprint_id == "none"
                else _object_id(sprint_id, "sprintId")
            ),
            labels=normalized_labels,
            blocked=blocked,
            parent_issue_id=(
                _object_id(parent_issue_id, "parentIssueId") if parent_issue_id else None
            ),
            text=(q or "").strip() or None,
            sort=parse_sort(sort, ISSUE_SORT_FIELDS, DEFAULT_ISSUE_SORT),
        )
