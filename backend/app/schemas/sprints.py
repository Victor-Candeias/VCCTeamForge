from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.domain.sprints import SPRINT_GOAL_MAX_LENGTH, SPRINT_NAME_MAX_LENGTH, SprintStatus
from app.schemas.base import ApiModel


class SprintCreate(ApiModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str = Field(min_length=1, max_length=SPRINT_NAME_MAX_LENGTH)
    goal: str = Field(default="", max_length=SPRINT_GOAL_MAX_LENGTH)
    start_date: date
    # Omissão: início + duração configurada no projeto.
    end_date: date | None = None


class SprintUpdate(ApiModel):
    """Campos omitidos ficam inalterados; o projeto e o estado não se editam aqui."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=SPRINT_NAME_MAX_LENGTH)
    goal: str | None = Field(default=None, max_length=SPRINT_GOAL_MAX_LENGTH)
    start_date: date | None = None
    end_date: date | None = None


class SprintResponse(ApiModel):
    id: str
    project_id: str
    name: str
    goal: str
    status: SprintStatus
    start_date: date
    end_date: date
    duration_days: int
    committed_story_points: float | None
    committed_issue_count: int | None
    started_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    can_edit: bool
