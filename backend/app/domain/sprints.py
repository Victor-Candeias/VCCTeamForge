"""Regras de domínio dos sprints (README §4.4 e §5.4)."""

from datetime import date, timedelta
from enum import StrEnum

from app.domain.permissions import Permission
from app.domain.projects import SPRINT_DURATION_MAX_DAYS
from app.domain.users import User

SPRINT_NAME_MAX_LENGTH = 80
SPRINT_GOAL_MAX_LENGTH = 1000


class SprintStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"


# Sprints que ocupam o calendário do projeto (não se podem sobrepor).
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
