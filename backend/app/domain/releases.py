"""Releases e checklists (DEV-022)."""

import re
from dataclasses import dataclass
from enum import StrEnum

from app.domain.permissions import Permission
from app.domain.users import User

RELEASE_NAME_MAX_LENGTH = 40
RELEASE_NAME_PATTERN = re.compile(r"^[0-9A-Za-z._+-]+$")
RELEASE_DESCRIPTION_MAX_LENGTH = 5000
RELEASE_NOTES_MAX_LENGTH = 20000
RELEASE_ISSUES_MAX = 500
RELEASE_KNOWN_BUGS_MAX = 100
RELEASE_TEST_PLANS_MAX = 50
CHECKLIST_MAX = 30
CHECKLIST_LABEL_MAX_LENGTH = 200
COMMENT_MAX_LENGTH = 2000
HISTORY_MAX = 500


class ReleaseStatus(StrEnum):
    DRAFT = "draft"
    READY_FOR_QA = "ready_for_qa"
    APPROVED = "approved"
    RELEASED = "released"


EDITABLE_STATUSES = frozenset({ReleaseStatus.DRAFT, ReleaseStatus.READY_FOR_QA})


class ReleaseCriterion(StrEnum):
    ISSUES_DONE = "issuesDone"
    TESTS_PASSED = "testsPassed"
    NO_OPEN_CRITICAL_BUGS = "noOpenCriticalBugs"


CRITERIA_LABELS = {
    ReleaseCriterion.ISSUES_DONE: "Todas as issues incluídas concluídas",
    ReleaseCriterion.TESTS_PASSED: "Testes dos planos associados aprovados",
    ReleaseCriterion.NO_OPEN_CRITICAL_BUGS: "Sem bugs críticos em aberto",
}

DEFAULT_CRITERIA = {criterion.value: True for criterion in ReleaseCriterion}

# (rótulo, obrigatório) usados quando o projeto ainda não tem releases.
DEFAULT_RELEASE_CHECKLIST: tuple[tuple[str, bool], ...] = (
    ("Testes de regressão executados", True),
    ("Notas de release revistas", True),
    ("Bugs conhecidos documentados", True),
    ("Plano de rollback definido", False),
)


@dataclass(frozen=True)
class Transition:
    action: str
    permissions: tuple[Permission, ...]
    comment_required: bool = False


_MANAGE = (Permission.RELEASES_MANAGE,)
_REVIEW = (Permission.RELEASES_MANAGE, Permission.RELEASES_APPROVE)

TRANSITIONS: dict[tuple[ReleaseStatus, ReleaseStatus], Transition] = {
    (ReleaseStatus.DRAFT, ReleaseStatus.READY_FOR_QA): Transition("submitted", _MANAGE),
    (ReleaseStatus.READY_FOR_QA, ReleaseStatus.APPROVED): Transition(
        "approved", (Permission.RELEASES_APPROVE,)
    ),
    (ReleaseStatus.READY_FOR_QA, ReleaseStatus.DRAFT): Transition(
        "rejected", _REVIEW, comment_required=True
    ),
    (ReleaseStatus.APPROVED, ReleaseStatus.RELEASED): Transition("released", _MANAGE),
    (ReleaseStatus.APPROVED, ReleaseStatus.DRAFT): Transition(
        "reopened", _REVIEW, comment_required=True
    ),
}


def can_transition(user: User, transition: Transition) -> bool:
    """Basta uma das permissões indicadas na transição."""
    return any(user.has_permissions(permission) for permission in transition.permissions)


def release_name_key(name: str) -> str:
    return name.casefold()
