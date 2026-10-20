from datetime import date, datetime

from app.domain.issues import IssueStatus
from app.domain.sprints import SprintStatus
from app.schemas.base import ApiModel


class SprintReportKpis(ApiModel):
    committed_issue_count: int
    committed_story_points: float
    issue_count: int
    story_points: float
    unestimated_count: int
    completed_issue_count: int
    completed_story_points: float
    remaining_story_points: float
    # ``None`` quando o âmbito não tem story points.
    progress_percent: float | None
    total_days: int
    elapsed_days: int
    remaining_days: int
    blocked_count: int
    added_count: int
    removed_count: int


class BurndownPoint(ApiModel):
    day: date
    ideal: float
    # ``None`` antes do primeiro snapshot ou em dias futuros.
    remaining: float | None
    scope: float | None


class StatusBreakdown(ApiModel):
    status: IssueStatus
    issue_count: int
    story_points: float


class BlockedIssue(ApiModel):
    issue_id: str
    key: str
    title: str
    status: IssueStatus
    block_reason: str | None
    blocked_at: datetime | None


class VelocityEntry(ApiModel):
    sprint_id: str
    name: str
    committed_story_points: float
    completed_story_points: float
    committed_completed_story_points: float
    # Concluído do compromisso / compromisso; ``None`` sem compromisso.
    predictability_percent: float | None


class SprintReport(ApiModel):
    sprint_id: str
    name: str
    goal: str
    status: SprintStatus
    start_date: date
    end_date: date
    as_of: datetime
    kpis: SprintReportKpis
    burndown: list[BurndownPoint]
    status_breakdown: list[StatusBreakdown]
    blocked_issues: list[BlockedIssue]
    velocity: list[VelocityEntry]
    average_velocity: float | None
