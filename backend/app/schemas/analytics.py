from datetime import date, datetime

from pydantic import Field

from app.domain.common import Priority
from app.domain.issues import IssueStatus, IssueType
from app.domain.releases import ReleaseStatus
from app.domain.sprints import SprintStatus
from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel
from app.schemas.reports import StatusBreakdown, VelocityEntry


class AnalyticsKpis(ApiModel):
    open_count: int
    in_progress_count: int
    blocked_count: int
    done_count: int
    critical_bug_count: int
    open_story_points: float
    # Aprovados / (aprovados + falhados + bloqueados); ``None`` sem execuções relevantes.
    test_pass_rate: float | None
    test_run_count: int


class IssueRef(ApiModel):
    id: str
    key: str
    title: str
    project_id: str
    type: IssueType
    status: IssueStatus
    priority: Priority
    assignee: UserSummary | None
    # Data relevante para o contexto (bloqueio, última atualização ou criação).
    since: datetime
    age_days: int


class AlertGroup(ApiModel):
    kind: str
    label: str
    total: int
    issues: list[IssueRef]


class ActiveSprintSummary(ApiModel):
    sprint_id: str
    project_id: str
    project_key: str
    project_name: str
    name: str
    goal: str
    start_date: date
    end_date: date
    remaining_days: int
    issue_count: int
    completed_issue_count: int
    story_points: float
    completed_story_points: float
    progress_percent: float | None


class MyWork(ApiModel):
    open_count: int
    in_progress_count: int
    blocked_count: int
    issues: list[IssueRef]


class TrendPoint(ApiModel):
    day: date
    open_count: int
    in_progress_count: int
    blocked_count: int
    done_count: int
    critical_bug_count: int
    open_story_points: float


class DashboardOverview(ApiModel):
    project_id: str | None
    project_count: int
    kpis: AnalyticsKpis
    status_breakdown: list[StatusBreakdown]
    active_sprints: list[ActiveSprintSummary]
    alerts: list[AlertGroup]
    my_work: MyWork
    trend: list[TrendPoint]
    generated_at: datetime


class MetricsFilters(ApiModel):
    sprint_id: str | None
    type: IssueType | None
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")


class DurationMetric(ApiModel):
    count: int
    average_days: float | None
    median_days: float | None
    p85_days: float | None


class AgingBucket(ApiModel):
    label: str
    min_days: int
    max_days: int | None
    count: int


class AgingMetric(ApiModel):
    buckets: list[AgingBucket]
    oldest: list[IssueRef]


class BugSeverityRow(ApiModel):
    priority: Priority
    open: int
    done: int
    total: int


class QaMetric(ApiModel):
    run_count: int
    counts: dict[str, int]
    pass_rate: float | None


class ReleaseQualityRow(ApiModel):
    release_id: str
    name: str
    status: ReleaseStatus
    planned_date: date | None
    released_at: datetime | None
    issue_count: int
    done_issue_count: int
    known_bug_count: int
    open_bug_count: int
    open_critical_bug_count: int
    test_pass_rate: float | None
    ready: bool


class WorkloadRow(ApiModel):
    # ``None`` agrupa as issues sem responsável.
    assignee: UserSummary | None
    open_count: int
    in_progress_count: int
    blocked_count: int
    open_story_points: float


class VelocityMetric(ApiModel):
    sprints: list[VelocityEntry]
    average_velocity: float | None
    average_predictability_percent: float | None


class SprintOption(ApiModel):
    id: str
    name: str
    status: SprintStatus


class ProjectMetrics(ApiModel):
    project_id: str
    filters: MetricsFilters
    kpis: AnalyticsKpis
    status_breakdown: list[StatusBreakdown]
    velocity: VelocityMetric
    lead_time: DurationMetric
    cycle_time: DurationMetric
    aging: AgingMetric
    bug_severity: list[BugSeverityRow]
    qa: QaMetric
    releases: list[ReleaseQualityRow]
    workload: list[WorkloadRow]
    trend: list[TrendPoint]
    sprints: list[SprintOption]
    generated_at: datetime


class ReportSnapshot(ApiModel):
    project_id: str
    day: date
    kpis: AnalyticsKpis
    status_breakdown: list[StatusBreakdown]
    taken_at: datetime
