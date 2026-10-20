"""Regras das métricas e do dashboard (README §4.1, §4.7 e §9; DEV-023)."""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean, median

from app.domain.issues import IssueStatus

# Alertas do dashboard.
BLOCKED_ALERT_DAYS = 3
STALE_ALERT_DAYS = 14
ALERT_ISSUE_LIMIT = 10
MY_WORK_LIMIT = 10

# Janela das execuções de teste usadas no pass rate do dashboard.
PASS_RATE_WINDOW_DAYS = 30
DASHBOARD_TREND_DAYS = 30

# Métricas por projeto.
DEFAULT_PERIOD_DAYS = 90
MAX_PERIOD_DAYS = 366
VELOCITY_SPRINT_LIMIT = 10
RELEASE_LIMIT = 10
OLDEST_ISSUE_LIMIT = 10

IN_PROGRESS_STATUSES = frozenset(
    {IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, IssueStatus.TESTING}
)

# (rótulo, dias mínimos, dias máximos inclusive ou ``None`` sem limite).
AGING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("0–7 dias", 0, 7),
    ("8–30 dias", 8, 30),
    ("31–90 dias", 31, 90),
    ("> 90 dias", 91, None),
)


class AnalyticsRuleError(ValueError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class Period:
    first: date
    last: date


def resolve_period(first: date | None, last: date | None, today: date) -> Period:
    """Período das métricas: por omissão os últimos 90 dias até hoje (inclusive)."""
    last = last or today
    first = first or last - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if first > last:
        raise AnalyticsRuleError("A data inicial tem de ser anterior à final", field="from")
    if (last - first).days + 1 > MAX_PERIOD_DAYS:
        raise AnalyticsRuleError(f"O período não pode exceder {MAX_PERIOD_DAYS} dias", field="from")
    return Period(first, last)


def aging_bucket(days: int) -> int:
    """Índice do intervalo de ``AGING_BUCKETS`` para uma idade em dias."""
    for index, (_, low, high) in enumerate(AGING_BUCKETS):
        if days >= low and (high is None or days <= high):
            return index
    return 0


def percentile(values: list[float], fraction: float) -> float:
    """Percentil por interpolação linear (``values`` não vazio)."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


@dataclass(frozen=True)
class DurationStats:
    count: int
    average_days: float | None
    median_days: float | None
    p85_days: float | None


def duration_stats(values: list[float]) -> DurationStats:
    if not values:
        return DurationStats(0, None, None, None)
    return DurationStats(
        count=len(values),
        average_days=round(mean(values), 1),
        median_days=round(median(values), 1),
        p85_days=round(percentile(values, 0.85), 1),
    )
