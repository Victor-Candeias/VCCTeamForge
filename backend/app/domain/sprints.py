"""Regras de domínio dos sprints (README §4.4 e §5.4)."""

from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from app.domain.issues import IssueStatus, IssueType
from app.domain.permissions import Permission
from app.domain.projects import SPRINT_DURATION_MAX_DAYS
from app.domain.users import User

SPRINT_NAME_MAX_LENGTH = 80
SPRINT_GOAL_MAX_LENGTH = 1000
SPRINT_ISSUES_MAX = 300
SPRINT_ISSUES_PER_REQUEST_MAX = 50
CAPACITY_MAX = 1000
RETROSPECTIVE_TEXT_MAX_LENGTH = 5000


class SprintStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"


# Sprints que ocupam o calendário do projeto (não se podem sobrepor) e aceitam planeamento.
OPEN_STATUSES = frozenset({SprintStatus.PLANNED, SprintStatus.ACTIVE})


class SprintRuleError(ValueError):
    """Violação de uma regra de domínio; ``field`` indica o campo em causa."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def name_key(name: str) -> str:
    """Chave de unicidade do nome dentro do projeto (sem distinção de maiúsculas)."""
    return " ".join(name.split()).casefold()


def default_end_date(start: date, duration_days: int) -> date:
    """Fim inclusivo para a duração (em dias) configurada no projeto."""
    return start + timedelta(days=max(duration_days, 1) - 1)


def duration_days(start: date, end: date) -> int:
    return (end - start).days + 1


def validate_dates(start: date, end: date) -> None:
    if end < start:
        raise SprintRuleError("A data de fim não pode ser anterior à data de início", "endDate")
    if duration_days(start, end) > SPRINT_DURATION_MAX_DAYS:
        raise SprintRuleError(
            f"Um sprint dura no máximo {SPRINT_DURATION_MAX_DAYS} dias", "endDate"
        )


def can_manage_sprints(user: User) -> bool:
    return user.has_permissions(Permission.SPRINTS_MANAGE)


def validate_capacity(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0 or value > CAPACITY_MAX or Decimal(str(value)) % Decimal("0.5") != 0:
        raise SprintRuleError(
            f"Capacidade entre 0 e {CAPACITY_MAX} story points, em múltiplos de 0,5",
            "capacityStoryPoints",
        )
    return float(value)


def validate_plannable(issue_type: IssueType | str, status: IssueStatus | str) -> None:
    """Só entram em sprints issues por concluir; os epics agregam trabalho de vários sprints."""
    if IssueType(issue_type) is IssueType.EPIC:
        raise SprintRuleError("Um epic não pode ser associado a um sprint", "issueIds")
    if IssueStatus(status) is IssueStatus.DONE:
        raise SprintRuleError("Uma issue concluída não pode ser associada a um sprint", "issueIds")


def validate_startable(
    status: SprintStatus | str, end: date, today: date, issue_count: int
) -> None:
    if SprintStatus(status) is not SprintStatus.PLANNED:
        raise SprintRuleError("Só um sprint planeado pode ser iniciado", "status")
    if end < today:
        raise SprintRuleError(
            "A data de fim já passou: ajuste as datas antes de iniciar", "endDate"
        )
    if issue_count == 0:
        raise SprintRuleError("Associe pelo menos uma issue antes de iniciar o sprint", "issueIds")


def validate_closable(status: SprintStatus | str) -> None:
    if SprintStatus(status) is not SprintStatus.ACTIVE:
        raise SprintRuleError("Só um sprint ativo pode ser fechado", "status")
