"""Regras de domínio dos casos e planos de teste (README §4.5 e §5.1)."""

import re
from enum import StrEnum

from bson import ObjectId

from app.domain.permissions import Permission
from app.domain.users import User

TEST_CASE_TITLE_MAX_LENGTH = 200
TEST_CASE_TEXT_MAX_LENGTH = 5000
TEST_CASE_EXPECTED_RESULT_MAX_LENGTH = 2000
TEST_STEPS_MAX = 50
TEST_STEP_TEXT_MAX_LENGTH = 1000
TEST_PLAN_NAME_MAX_LENGTH = 120
TEST_PLAN_DESCRIPTION_MAX_LENGTH = 5000
TEST_PLAN_CASES_MAX = 500
LINKED_ISSUES_MAX = 20

TEST_CASE_KEY_PATTERN = re.compile(r"TC-(\d{1,9})", re.IGNORECASE)


class TestCaseStatus(StrEnum):
    __test__ = False

    DRAFT = "draft"
    READY = "ready"
    DEPRECATED = "deprecated"


class TestPlanStatus(StrEnum):
    __test__ = False

    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


def case_counter_name(project_id: ObjectId) -> str:
    return f"test_cases:{project_id}"


def case_key(number: int) -> str:
    return f"TC-{number}"


def plan_name_key(name: str) -> str:
    """Chave de unicidade do nome do plano no projeto (sem distinção de maiúsculas)."""
    return " ".join(name.split()).casefold()


def can_manage_tests(user: User) -> bool:
    return user.has_permissions(Permission.TESTS_MANAGE)


# Execuções (DEV-021) -----------------------------------------------------------------------

TEST_RUN_TEXT_MAX_LENGTH = 5000
TEST_RUN_ENVIRONMENT_MAX_LENGTH = 200
TEST_RUN_BUGS_MAX = 20


class TestRunResult(StrEnum):
    __test__ = False

    PASS = "pass"  # noqa: S105 - resultado de teste, não é uma password
    FAIL = "fail"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"
    SKIPPED = "skipped"


# Resultados que contam para a taxa de aprovação (README §9 "QA Pass Rate").
PASS_RATE_RESULTS = frozenset({TestRunResult.PASS, TestRunResult.FAIL, TestRunResult.BLOCKED})


def pass_rate(counts: dict[str, int]) -> float | None:
    """Aprovados / (aprovados + falhados + bloqueados); ``skipped``/``not_run`` não contam."""
    relevant = sum(counts.get(result.value, 0) for result in PASS_RATE_RESULTS)
    if relevant == 0:
        return None
    return round(counts.get(TestRunResult.PASS.value, 0) / relevant, 4)


def can_execute_tests(user: User) -> bool:
    return user.has_permissions(Permission.TESTS_EXECUTE)


def can_edit_test_run(user: User, run: dict) -> bool:
    if user.has_permissions(Permission.TESTS_MANAGE):
        return True
    return can_execute_tests(user) and run.get("executedBy") == user.id
