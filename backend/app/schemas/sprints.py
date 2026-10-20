from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.domain.issues import IssueStatus, IssueType
from app.domain.sprints import (
    CAPACITY_MAX,
    SPRINT_GOAL_MAX_LENGTH,
    SPRINT_ISSUES_PER_REQUEST_MAX,
    SPRINT_NAME_MAX_LENGTH,
    SprintStatus,
)
from app.schemas.base import ApiModel


class SprintCreate(ApiModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str = Field(min_length=1, max_length=SPRINT_NAME_MAX_LENGTH)
    goal: str = Field(default="", max_length=SPRINT_GOAL_MAX_LENGTH)
    start_date: date
    # Omissão: início + duração configurada no projeto.
    end_date: date | None = None
    capacity_story_points: float | None = Field(default=None, ge=0, le=CAPACITY_MAX)


class SprintUpdate(ApiModel):
    """Campos omitidos ficam inalterados; o projeto e o estado não se editam aqui."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=SPRINT_NAME_MAX_LENGTH)
    goal: str | None = Field(default=None, max_length=SPRINT_GOAL_MAX_LENGTH)
    start_date: date | None = None
    end_date: date | None = None
    capacity_story_points: float | None = Field(default=None, ge=0, le=CAPACITY_MAX)


class SprintIssuesAdd(ApiModel):
    model_config = ConfigDict(extra="forbid")

    issue_ids: list[str] = Field(min_length=1, max_length=SPRINT_ISSUES_PER_REQUEST_MAX)


class SprintScope(ApiModel):
    """Totais atuais das issues associadas ao sprint."""

    issue_count: int = 0
    story_points: float = 0
    unestimated_count: int = 0
    completed_issue_count: int = 0
    completed_story_points: float = 0


class SprintResponse(ApiModel):
    id: str
    project_id: str
    name: str
    goal: str
    status: SprintStatus
    start_date: date
    end_date: date
    duration_days: int
    capacity_story_points: float | None
    scope: SprintScope
    committed_story_points: float | None
    committed_issue_count: int | None
    started_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    can_edit: bool


class SprintStart(ApiModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)


class CommittedIssue(ApiModel):
    """Issue do compromisso: valores no início e situação atual."""

    issue_id: str
    key: str
    title: str
    type: IssueType
    status: IssueStatus
    story_points: float | None
    current_status: IssueStatus | None
    current_story_points: float | None
    in_sprint: bool


class AddedIssue(ApiModel):
    issue_id: str
    key: str
    title: str
    type: IssueType
    status: IssueStatus
    story_points: float | None


class SprintCommitment(ApiModel):
    sprint_id: str
    taken_at: datetime
    issue_count: int
    story_points: float
    unestimated_count: int
    removed_count: int
    added_count: int
    added_story_points: float
    issues: list[CommittedIssue]
    added: list[AddedIssue]
