from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.domain.common import Priority
from app.domain.projects import SPRINT_DURATION_MAX_DAYS, SPRINT_DURATION_MIN_DAYS, ProjectStatus
from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel

EditableStatus = Literal["active", "on_hold", "completed"]


class ProjectSettingsInput(ApiModel):
    model_config = ConfigDict(extra="forbid")

    sprint_duration_days: int = Field(ge=SPRINT_DURATION_MIN_DAYS, le=SPRINT_DURATION_MAX_DAYS)


class ProjectCreate(ApiModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    status: EditableStatus = "active"
    priority: Priority = Priority.MEDIUM
    lead_user_id: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    member_ids: list[str] = Field(default_factory=list, max_length=200)
    settings: ProjectSettingsInput | None = None


class ProjectUpdate(ApiModel):
    """Campos omitidos ficam inalterados; ``key`` e membros não são editáveis aqui."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    status: EditableStatus | None = None
    priority: Priority | None = None
    lead_user_id: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    settings: ProjectSettingsInput | None = None


class VersionInput(ApiModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)


class MemberAdd(VersionInput):
    user_id: str


class ProjectSettings(ApiModel):
    methodology: str
    sprint_duration_days: int
    estimation_type: str


class ProjectResponse(ApiModel):
    id: str
    key: str
    name: str
    description: str
    status: ProjectStatus
    priority: Priority
    lead: UserSummary | None
    start_date: date | None
    target_date: date | None
    member_count: int
    settings: ProjectSettings
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    version: int
    can_manage: bool


class MemberResponse(UserSummary):
    is_lead: bool


class ProjectMembersResponse(ApiModel):
    version: int
    can_manage: bool
    members: list[MemberResponse]
