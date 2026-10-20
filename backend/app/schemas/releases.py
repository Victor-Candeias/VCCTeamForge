from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.domain.qa import TestRunResult
from app.domain.releases import (
    CHECKLIST_LABEL_MAX_LENGTH,
    CHECKLIST_MAX,
    COMMENT_MAX_LENGTH,
    RELEASE_DESCRIPTION_MAX_LENGTH,
    RELEASE_ISSUES_MAX,
    RELEASE_KNOWN_BUGS_MAX,
    RELEASE_NAME_MAX_LENGTH,
    RELEASE_NOTES_MAX_LENGTH,
    RELEASE_TEST_PLANS_MAX,
    ReleaseCriterion,
    ReleaseStatus,
)
from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel
from app.schemas.issues import IssueRef


class ChecklistItemInput(ApiModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, max_length=40)
    label: str = Field(min_length=1, max_length=CHECKLIST_LABEL_MAX_LENGTH)
    required: bool = False
    done: bool = False


class ReleaseCriteria(ApiModel):
    model_config = ConfigDict(extra="forbid")

    issues_done: bool = True
    tests_passed: bool = True
    no_open_critical_bugs: bool = True


class ReleaseCreate(ApiModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str = Field(min_length=1, max_length=RELEASE_NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=RELEASE_DESCRIPTION_MAX_LENGTH)
    notes: str = Field(default="", max_length=RELEASE_NOTES_MAX_LENGTH)
    planned_date: date | None = None
    issue_ids: list[str] = Field(default_factory=list, max_length=RELEASE_ISSUES_MAX)
    known_bug_ids: list[str] = Field(default_factory=list, max_length=RELEASE_KNOWN_BUGS_MAX)
    test_plan_ids: list[str] = Field(default_factory=list, max_length=RELEASE_TEST_PLANS_MAX)
    checklist: list[ChecklistItemInput] | None = Field(default=None, max_length=CHECKLIST_MAX)
    criteria: ReleaseCriteria = Field(default_factory=ReleaseCriteria)


class ReleaseUpdate(ApiModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=RELEASE_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=RELEASE_DESCRIPTION_MAX_LENGTH)
    notes: str | None = Field(default=None, max_length=RELEASE_NOTES_MAX_LENGTH)
    planned_date: date | None = None
    issue_ids: list[str] | None = Field(default=None, max_length=RELEASE_ISSUES_MAX)
    known_bug_ids: list[str] | None = Field(default=None, max_length=RELEASE_KNOWN_BUGS_MAX)
    test_plan_ids: list[str] | None = Field(default=None, max_length=RELEASE_TEST_PLANS_MAX)
    checklist: list[ChecklistItemInput] | None = Field(default=None, max_length=CHECKLIST_MAX)
    criteria: ReleaseCriteria | None = None


class ReleaseTransition(ApiModel):
    model_config = ConfigDict(extra="forbid")

    to: ReleaseStatus
    comment: str = Field(default="", max_length=COMMENT_MAX_LENGTH)
    version: int = Field(ge=1)


class ChecklistItem(ApiModel):
    id: str
    label: str
    required: bool
    done: bool
    done_by: UserSummary | None = None
    done_at: datetime | None = None


class TestPlanRef(ApiModel):
    __test__ = False

    id: str
    name: str
    status: str


class ReleaseSummary(ApiModel):
    id: str
    project_id: str
    name: str
    status: ReleaseStatus
    planned_date: date | None
    released_at: datetime | None
    issue_count: int
    known_bug_count: int
    checklist_done: int
    checklist_total: int
    created_at: datetime
    updated_at: datetime
    version: int


class CriterionResult(ApiModel):
    key: ReleaseCriterion
    label: str
    enabled: bool
    passed: bool
    detail: str


class ReleaseIssueQuality(ApiModel):
    total: int
    done: int


class ReleaseBugQuality(ApiModel):
    total: int
    open: int
    open_critical: int


class ReleaseTestQuality(ApiModel):
    plans: int
    total_cases: int
    executed_cases: int
    counts: dict[TestRunResult, int]
    pass_rate: float | None
    regressions: int


class ReleaseQuality(ApiModel):
    issues: ReleaseIssueQuality
    known_bugs: ReleaseBugQuality
    tests: ReleaseTestQuality
    criteria: list[CriterionResult]
    ready: bool


class ReleaseHistoryEntry(ApiModel):
    action: str
    from_status: ReleaseStatus | None = None
    to_status: ReleaseStatus | None = None
    fields: list[str] = Field(default_factory=list)
    comment: str = ""
    user: UserSummary | None
    at: datetime


class ReleaseResponse(ReleaseSummary):
    description: str
    notes: str
    issues: list[IssueRef]
    known_bugs: list[IssueRef]
    test_plans: list[TestPlanRef]
    checklist: list[ChecklistItem]
    criteria: ReleaseCriteria
    quality: ReleaseQuality
    history: list[ReleaseHistoryEntry]
    can_edit: bool
    available_transitions: list[ReleaseStatus]
