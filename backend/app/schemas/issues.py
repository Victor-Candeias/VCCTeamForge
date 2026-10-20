from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.domain.common import Priority
from app.domain.issues import (
    ACCEPTANCE_CRITERIA_MAX,
    BLOCK_REASON_MAX_LENGTH,
    DEPENDENCIES_MAX,
    DESCRIPTION_MAX_LENGTH,
    LABELS_MAX,
    STORY_POINTS_MAX,
    TITLE_MAX_LENGTH,
    IssueStatus,
    IssueType,
)
from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel


class _IssueFields(ApiModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    priority: Priority | None = None
    assignee_id: str | None = None
    parent_issue_id: str | None = None
    story_points: float | None = Field(default=None, ge=0, le=STORY_POINTS_MAX)
    labels: list[str] | None = Field(default=None, max_length=LABELS_MAX * 2)
    acceptance_criteria: list[str] | None = Field(default=None, max_length=ACCEPTANCE_CRITERIA_MAX)
    depends_on_issue_ids: list[str] | None = Field(default=None, max_length=DEPENDENCIES_MAX)
    due_date: date | None = None


class IssueCreate(_IssueFields):
    project_id: str
    type: IssueType
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)


class IssueUpdate(_IssueFields):
    """Campos omitidos ficam inalterados; ``type`` e projeto não são editáveis."""

    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    status: IssueStatus | None = None
    blocked: bool | None = None
    block_reason: str | None = Field(default=None, max_length=BLOCK_REASON_MAX_LENGTH)


class IssueRef(ApiModel):
    id: str
    key: str
    title: str
    type: IssueType
    status: IssueStatus


class IssueSummary(ApiModel):
    id: str
    project_id: str
    key: str
    number: int
    type: IssueType
    title: str
    status: IssueStatus
    priority: Priority
    assignee: UserSummary | None
    story_points: float | None
    labels: list[str]
    blocked: bool
    due_date: date | None
    parent_issue_id: str | None
    sprint_id: str | None
    updated_at: datetime
    version: int


class Issue(IssueSummary):
    project_key: str
    description: str
    reporter: UserSummary | None
    parent: IssueRef | None
    acceptance_criteria: list[str]
    depends_on: list[IssueRef]
    block_reason: str | None
    blocked_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    can_edit: bool
    allowed_transitions: list[IssueStatus]
