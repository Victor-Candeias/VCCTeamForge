"""Regras de domínio das issues (README §4.3, §5.3 e §6)."""

from collections.abc import Iterable, Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.domain.permissions import Permission, Role
from app.domain.users import User

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 20_000
STORY_POINTS_MAX = 100
LABELS_MAX = 20
LABEL_MAX_LENGTH = 40
ACCEPTANCE_CRITERIA_MAX = 50
ACCEPTANCE_CRITERION_MAX_LENGTH = 500
DEPENDENCIES_MAX = 50
BLOCK_REASON_MAX_LENGTH = 500


class IssueType(StrEnum):
    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    BUG = "bug"
    SPIKE = "spike"
    IMPROVEMENT = "improvement"
    SUBTASK = "subtask"


class IssueStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DONE = "done"


ALLOWED_TRANSITIONS: dict[IssueStatus, frozenset[IssueStatus]] = {
    IssueStatus.TODO: frozenset({IssueStatus.IN_PROGRESS}),
    IssueStatus.IN_PROGRESS: frozenset(
        {IssueStatus.TODO, IssueStatus.CODE_REVIEW, IssueStatus.TESTING, IssueStatus.DONE}
    ),
    IssueStatus.CODE_REVIEW: frozenset(
        {IssueStatus.IN_PROGRESS, IssueStatus.TESTING, IssueStatus.DONE}
    ),
    IssueStatus.TESTING: frozenset(
        {IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, IssueStatus.DONE}
    ),
    IssueStatus.DONE: frozenset({IssueStatus.IN_PROGRESS}),
}

# Valor gravado em cada issue para ordenar pelo fluxo (todo=1 … done=5).
STATUS_RANK: dict[IssueStatus, int] = {
    status: position for position, status in enumerate(IssueStatus, start=1)
}

# Tipos que podem ser pai de uma subtask.
SUBTASK_PARENT_TYPES = frozenset(
    {
        IssueType.STORY,
        IssueType.TASK,
        IssueType.BUG,
        IssueType.SPIKE,
        IssueType.IMPROVEMENT,
    }
)

# Perfis que editam qualquer issue dos projetos a que têm acesso.
FULL_EDIT_ROLES = frozenset({Role.ADMIN, Role.TECH_LEAD})


class IssueRuleError(ValueError):
    """Violação de uma regra de domínio; ``field`` indica o campo em causa."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def allowed_transitions(status: IssueStatus | str) -> list[IssueStatus]:
    current = IssueStatus(status)
    return [target for target in IssueStatus if target in ALLOWED_TRANSITIONS[current]]


def validate_transition(current: IssueStatus | str, target: IssueStatus | str) -> None:
    current, target = IssueStatus(current), IssueStatus(target)
    if current != target and target not in ALLOWED_TRANSITIONS[current]:
        raise IssueRuleError(f"Transição de estado inválida: {current} → {target}", "status")


def normalize_labels(labels: Iterable[str]) -> list[str]:
    """Minúsculas, sem espaços nas extremidades e sem repetidos (mantém a ordem)."""
    result: list[str] = []
    for raw in labels:
        label = raw.strip().lower()
        if not label or len(label) > LABEL_MAX_LENGTH:
            raise IssueRuleError(
                f"Cada label tem de ter 1 a {LABEL_MAX_LENGTH} caracteres", "labels"
            )
        if label not in result:
            result.append(label)
    if len(result) > LABELS_MAX:
        raise IssueRuleError(f"No máximo {LABELS_MAX} labels", "labels")
    return result


def normalize_acceptance_criteria(items: Iterable[str]) -> list[str]:
    result = [item.strip() for item in items if item.strip()]
    if len(result) > ACCEPTANCE_CRITERIA_MAX:
        raise IssueRuleError(
            f"No máximo {ACCEPTANCE_CRITERIA_MAX} critérios de aceitação", "acceptanceCriteria"
        )
    if any(len(item) > ACCEPTANCE_CRITERION_MAX_LENGTH for item in result):
        raise IssueRuleError(
            f"Cada critério tem no máximo {ACCEPTANCE_CRITERION_MAX_LENGTH} caracteres",
            "acceptanceCriteria",
        )
    return result


def validate_story_points(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0 or value > STORY_POINTS_MAX or Decimal(str(value)) % Decimal("0.5") != 0:
        raise IssueRuleError(
            f"Story points entre 0 e {STORY_POINTS_MAX}, em múltiplos de 0,5", "storyPoints"
        )
    return float(value)


def validate_parent(issue_type: IssueType | str, parent_type: IssueType | str | None) -> None:
    """Hierarquia: epic sem pai; subtask com pai não epic/subtask; restantes só sob epic."""
    issue_type = IssueType(issue_type)
    if issue_type is IssueType.EPIC:
        if parent_type is not None:
            raise IssueRuleError("Um epic não pode ter pai", "parentIssueId")
        return
    if issue_type is IssueType.SUBTASK:
        if parent_type is None:
            raise IssueRuleError("Uma subtask tem de ter uma issue pai", "parentIssueId")
        if IssueType(parent_type) not in SUBTASK_PARENT_TYPES:
            raise IssueRuleError(
                "O pai de uma subtask não pode ser um epic nem outra subtask", "parentIssueId"
            )
        return
    if parent_type is not None and IssueType(parent_type) is not IssueType.EPIC:
        raise IssueRuleError("Só um epic pode ser pai deste tipo de issue", "parentIssueId")


def can_create_issue_type(user: User, issue_type: IssueType | str) -> bool:
    if not user.has_permissions(Permission.ISSUES_WRITE):
        return False
    if user.role is Role.QA:
        return IssueType(issue_type) is IssueType.BUG
    return True


def can_edit_issue(user: User, issue: Mapping[str, Any]) -> bool:
    """Admin/Tech Lead editam qualquer issue; Developer/QA só as atribuídas ou reportadas."""
    if not user.has_permissions(Permission.ISSUES_WRITE):
        return False
    if user.role in FULL_EDIT_ROLES:
        return True
    return user.id in (issue.get("assigneeId"), issue.get("reporterId"))
