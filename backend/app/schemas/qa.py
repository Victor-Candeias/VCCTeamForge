from datetime import datetime

from pydantic import ConfigDict, Field

from app.domain.common import Priority
from app.domain.issues import LABELS_MAX, TITLE_MAX_LENGTH
from app.domain.qa import (
    LINKED_ISSUES_MAX,
    TEST_CASE_EXPECTED_RESULT_MAX_LENGTH,
    TEST_CASE_TEXT_MAX_LENGTH,
    TEST_CASE_TITLE_MAX_LENGTH,
    TEST_PLAN_CASES_MAX,
    TEST_PLAN_DESCRIPTION_MAX_LENGTH,
    TEST_PLAN_NAME_MAX_LENGTH,
    TEST_RUN_ENVIRONMENT_MAX_LENGTH,
    TEST_RUN_TEXT_MAX_LENGTH,
    TEST_STEP_TEXT_MAX_LENGTH,
    TEST_STEPS_MAX,
    TestCaseStatus,
    TestPlanStatus,
    TestRunResult,
)
from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel
from app.schemas.issues import IssueRef


class TestStep(ApiModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=TEST_STEP_TEXT_MAX_LENGTH)
    expected_result: str = Field(default="", max_length=TEST_STEP_TEXT_MAX_LENGTH)


# Casos de teste ----------------------------------------------------------------------------


class TestCaseCreate(ApiModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str = Field(min_length=1, max_length=TEST_CASE_TITLE_MAX_LENGTH)
    description: str = Field(default="", max_length=TEST_CASE_TEXT_MAX_LENGTH)
    preconditions: str = Field(default="", max_length=TEST_CASE_TEXT_MAX_LENGTH)
    steps: list[TestStep] = Field(min_length=1, max_length=TEST_STEPS_MAX)
    expected_result: str = Field(default="", max_length=TEST_CASE_EXPECTED_RESULT_MAX_LENGTH)
    priority: Priority = Priority.MEDIUM
    status: TestCaseStatus = TestCaseStatus.DRAFT
    labels: list[str] = Field(default_factory=list, max_length=LABELS_MAX)
    issue_ids: list[str] = Field(default_factory=list, max_length=LINKED_ISSUES_MAX)


class TestCaseUpdate(ApiModel):
    """Campos omitidos ficam inalterados; o projeto e o número não se editam."""

    __test__ = False
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=TEST_CASE_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=TEST_CASE_TEXT_MAX_LENGTH)
    preconditions: str | None = Field(default=None, max_length=TEST_CASE_TEXT_MAX_LENGTH)
    steps: list[TestStep] | None = Field(default=None, min_length=1, max_length=TEST_STEPS_MAX)
    expected_result: str | None = Field(
        default=None, max_length=TEST_CASE_EXPECTED_RESULT_MAX_LENGTH
    )
    priority: Priority | None = None
    status: TestCaseStatus | None = None
    labels: list[str] | None = Field(default=None, max_length=LABELS_MAX)
    issue_ids: list[str] | None = Field(default=None, max_length=LINKED_ISSUES_MAX)


class TestCaseSummary(ApiModel):
    __test__ = False

    id: str
    project_id: str
    key: str
    number: int
    title: str
    priority: Priority
    status: TestCaseStatus
    labels: list[str]
    step_count: int
    updated_at: datetime
    version: int


class TestCaseResponse(TestCaseSummary):
    __test__ = False

    description: str
    preconditions: str
    steps: list[TestStep]
    expected_result: str
    issues: list[IssueRef]
    created_at: datetime
    can_edit: bool


class TestCaseRef(ApiModel):
    __test__ = False

    id: str
    key: str
    title: str
    priority: Priority
    status: TestCaseStatus


# Planos de teste ---------------------------------------------------------------------------


class TestPlanCreate(ApiModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str = Field(min_length=1, max_length=TEST_PLAN_NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=TEST_PLAN_DESCRIPTION_MAX_LENGTH)
    status: TestPlanStatus = TestPlanStatus.DRAFT
    test_case_ids: list[str] = Field(default_factory=list, max_length=TEST_PLAN_CASES_MAX)
    issue_ids: list[str] = Field(default_factory=list, max_length=LINKED_ISSUES_MAX)


class TestPlanUpdate(ApiModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=TEST_PLAN_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=TEST_PLAN_DESCRIPTION_MAX_LENGTH)
    status: TestPlanStatus | None = None
    test_case_ids: list[str] | None = Field(default=None, max_length=TEST_PLAN_CASES_MAX)
    issue_ids: list[str] | None = Field(default=None, max_length=LINKED_ISSUES_MAX)


class TestPlanSummary(ApiModel):
    __test__ = False

    id: str
    project_id: str
    name: str
    description: str
    status: TestPlanStatus
    test_case_count: int
    created_at: datetime
    updated_at: datetime
    version: int


class TestPlanResponse(TestPlanSummary):
    __test__ = False

    test_cases: list[TestCaseRef]
    issues: list[IssueRef]
    can_edit: bool


# Execuções (DEV-021) -----------------------------------------------------------------------


class TestRunCreate(ApiModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid")

    test_case_id: str
    test_plan_id: str | None = None
    result: TestRunResult
    actual_result: str = Field(default="", max_length=TEST_RUN_TEXT_MAX_LENGTH)
    notes: str = Field(default="", max_length=TEST_RUN_TEXT_MAX_LENGTH)
    environment: str = Field(default="", max_length=TEST_RUN_ENVIRONMENT_MAX_LENGTH)
    executed_at: datetime | None = None


class TestRunUpdate(ApiModel):
    """O caso, o plano e o executor não se editam."""

    __test__ = False
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    result: TestRunResult | None = None
    actual_result: str | None = Field(default=None, max_length=TEST_RUN_TEXT_MAX_LENGTH)
    notes: str | None = Field(default=None, max_length=TEST_RUN_TEXT_MAX_LENGTH)
    environment: str | None = Field(default=None, max_length=TEST_RUN_ENVIRONMENT_MAX_LENGTH)


class TestRunSummary(ApiModel):
    __test__ = False

    id: str
    project_id: str
    test_case_id: str
    test_case_key: str
    test_case_title: str
    test_plan_id: str | None
    test_plan_name: str | None
    result: TestRunResult
    environment: str
    executed_by: UserSummary | None
    executed_at: datetime
    bug_count: int
    evidence_count: int
    version: int


class TestRunResponse(TestRunSummary):
    __test__ = False

    actual_result: str
    notes: str
    bugs: list[IssueRef]
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_add_evidence: bool
    can_create_bug: bool


class TestRunBugCreate(ApiModel):
    """Campos omitidos são pré-preenchidos a partir da execução."""

    __test__ = False
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    priority: Priority | None = None
    assignee_id: str | None = None


class TestRunEvidence(ApiModel):
    __test__ = False

    id: str
    test_run_id: str
    original_name: str
    content_type: str
    size: int
    sha256: str
    is_image: bool
    uploaded_by: UserSummary | None
    created_at: datetime
    can_delete: bool


class TestPlanCaseProgress(ApiModel):
    __test__ = False

    test_case: TestCaseRef
    last_run_id: str | None
    last_result: TestRunResult
    last_executed_at: datetime | None
    last_executed_by: UserSummary | None
    previous_result: TestRunResult | None
    regression: bool


class TestPlanProgress(ApiModel):
    __test__ = False

    test_plan_id: str
    total_cases: int
    counts: dict[TestRunResult, int]
    executed_cases: int
    pass_rate: float | None
    regressions: int
    cases: list[TestPlanCaseProgress]
