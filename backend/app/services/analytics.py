"""Dashboard geral, métricas por projeto e snapshots de relatório (DEV-023).

Leituras agregadas sobre os dados atuais; as tendências usam ``report_snapshots`` (um por
projeto e dia), gravados pelo comando ``report-snapshots`` ou a pedido do gestor do projeto.
"""

import logging
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError
from app.domain.analytics import (
    AGING_BUCKETS,
    ALERT_ISSUE_LIMIT,
    BLOCKED_ALERT_DAYS,
    DASHBOARD_TREND_DAYS,
    IN_PROGRESS_STATUSES,
    MY_WORK_LIMIT,
    OLDEST_ISSUE_LIMIT,
    PASS_RATE_WINDOW_DAYS,
    RELEASE_LIMIT,
    STALE_ALERT_DAYS,
    VELOCITY_SPRINT_LIMIT,
    AnalyticsRuleError,
    aging_bucket,
    duration_stats,
    resolve_period,
)
from app.domain.common import Priority
from app.domain.issues import IssueStatus, IssueType
from app.domain.projects import ProjectStatus, is_archived
from app.domain.qa import TestRunResult, pass_rate
from app.domain.sprints import SprintStatus
from app.domain.users import User
from app.repositories.analytics import AnalyticsRepository, ReportSnapshotRepository
from app.repositories.issues import IssueRepository
from app.repositories.projects import ProjectRepository
from app.repositories.releases import ReleaseRepository
from app.repositories.sprints import SprintRepository
from app.repositories.users import UserRepository
from app.schemas.analytics import (
    ActiveSprintSummary,
    AgingBucket,
    AgingMetric,
    AlertGroup,
    AnalyticsKpis,
    BugSeverityRow,
    DashboardOverview,
    DurationMetric,
    IssueRef,
    MetricsFilters,
    MyWork,
    ProjectMetrics,
    QaMetric,
    ReleaseQualityRow,
    ReportSnapshot,
    SprintOption,
    TrendPoint,
    VelocityMetric,
    WorkloadRow,
)
from app.schemas.auth import UserSummary
from app.schemas.reports import StatusBreakdown
from app.services.authorization import (
    accessible_projects_filter,
    ensure_project_access,
    ensure_project_manager,
)
from app.services.common import datetime_to_date
from app.services.releases import ReleaseService
from app.services.sprint_reports import velocity_entry

logger = logging.getLogger(__name__)

DONE = IssueStatus.DONE.value
NOT_DONE = {"$ne": DONE}
SECONDS_PER_DAY = 86_400

_ISSUE_REF_PROJECTION = {
    "key": 1,
    "title": 1,
    "projectId": 1,
    "type": 1,
    "status": 1,
    "priority": 1,
    "assigneeId": 1,
    "blockedAt": 1,
    "updatedAt": 1,
    "createdAt": 1,
}

ALERT_LABELS = {
    "blocked": f"Bloqueadas há mais de {BLOCKED_ALERT_DAYS} dias",
    "stale": f"Sem atualização há mais de {STALE_ALERT_DAYS} dias",
    "unassigned_critical_bugs": "Bugs críticos sem responsável",
}


def _round(value: float) -> float:
    return round(value, 2)


def _aware(value: datetime) -> datetime:
    """O PyMongo devolve datas sem fuso (são UTC)."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _days_between(start: datetime, end: datetime) -> float:
    return (_aware(end) - _aware(start)).total_seconds() / SECONDS_PER_DAY


def _midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _critical_bugs(query: dict[str, Any]) -> dict[str, Any]:
    return {
        **query,
        "type": IssueType.BUG.value,
        "priority": Priority.CRITICAL.value,
        "status": NOT_DONE,
    }


def _trend_point(day: datetime, kpis: dict[str, Any]) -> TrendPoint:
    return TrendPoint(
        day=day.date(),
        open_count=kpis.get("openCount", 0),
        in_progress_count=kpis.get("inProgressCount", 0),
        blocked_count=kpis.get("blockedCount", 0),
        done_count=kpis.get("doneCount", 0),
        critical_bug_count=kpis.get("criticalBugCount", 0),
        open_story_points=_round(kpis.get("openStoryPoints", 0)),
    )


class _AnalyticsService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.analytics = AnalyticsRepository(db)
        self.snapshots = ReportSnapshotRepository(db)
        self.projects = ProjectRepository(db)
        self.sprints = SprintRepository(db)
        self.users = UserRepository(db)

    def _get_project(self, user: User, project_id: ObjectId) -> dict[str, Any]:
        return dict(ensure_project_access(user, self.projects.find_by_id(project_id)))

    def _kpis(
        self,
        query: dict[str, Any],
        project_ids: list[ObjectId],
        since: datetime,
        until: datetime | None = None,
    ) -> tuple[AnalyticsKpis, list[StatusBreakdown]]:
        by_status = self.analytics.status_breakdown(query)
        empty = {"count": 0, "storyPoints": 0.0, "blocked": 0}
        rows = {status: by_status.get(status.value, empty) for status in IssueStatus}
        open_rows = [row for status, row in rows.items() if status != IssueStatus.DONE]
        counts = self.analytics.test_run_counts(project_ids, since, until)
        kpis = AnalyticsKpis(
            open_count=sum(int(row["count"]) for row in open_rows),
            in_progress_count=sum(int(rows[status]["count"]) for status in IN_PROGRESS_STATUSES),
            blocked_count=sum(int(row["blocked"]) for row in open_rows),
            done_count=int(rows[IssueStatus.DONE]["count"]),
            critical_bug_count=self.analytics.count_issues(_critical_bugs(query)),
            open_story_points=_round(sum(row["storyPoints"] for row in open_rows)),
            test_pass_rate=pass_rate(counts),
            test_run_count=sum(counts.values()),
        )
        breakdown = [
            StatusBreakdown(
                status=status,
                issue_count=int(row["count"]),
                story_points=_round(row["storyPoints"]),
            )
            for status, row in rows.items()
        ]
        return kpis, breakdown

    def _user_summaries(self, user_ids: Iterable[ObjectId | None]) -> dict[ObjectId, UserSummary]:
        found = self.users.find_by_ids([user_id for user_id in set(user_ids) if user_id])
        return {user_id: UserSummary.from_document(document) for user_id, document in found.items()}

    def _issue_refs(
        self, issues: list[dict[str, Any]], since_field: str, now: datetime
    ) -> list[IssueRef]:
        users = self._user_summaries(issue.get("assigneeId") for issue in issues)
        refs = []
        for issue in issues:
            since = issue.get(since_field) or issue["createdAt"]
            refs.append(
                IssueRef(
                    id=str(issue["_id"]),
                    key=issue["key"],
                    title=issue["title"],
                    project_id=str(issue["projectId"]),
                    type=issue["type"],
                    status=issue["status"],
                    priority=issue["priority"],
                    assignee=users.get(issue.get("assigneeId")),
                    since=since,
                    age_days=max(0, int(_days_between(since, now))),
                )
            )
        return refs


class DashboardService(_AnalyticsService):
    def overview(self, user: User, project_id: ObjectId | None) -> DashboardOverview:
        now = datetime.now(UTC)
        if project_id is not None:
            projects = [self._get_project(user, project_id)]
        else:
            projects = self.projects.search(
                {
                    **accessible_projects_filter(user),
                    "status": {"$ne": ProjectStatus.ARCHIVED.value},
                },
                sort=[("name", 1)],
                skip=0,
                limit=0,
            )
        project_ids = [project["_id"] for project in projects]
        base = {"projectId": {"$in": project_ids}}
        since = _midnight(now.date() - timedelta(days=PASS_RATE_WINDOW_DAYS - 1))
        kpis, breakdown = self._kpis(base, project_ids, since)
        trend_start = _midnight(now.date() - timedelta(days=DASHBOARD_TREND_DAYS - 1))

        return DashboardOverview(
            project_id=str(project_id) if project_id else None,
            project_count=len(projects),
            kpis=kpis,
            status_breakdown=breakdown,
            active_sprints=self._active_sprints(projects, now.date()),
            alerts=self._alerts(base, now),
            my_work=self._my_work(user, base, now),
            trend=[
                _trend_point(row["_id"], row)
                for row in self.snapshots.daily_totals(project_ids, trend_start)
            ],
            generated_at=now,
        )

    def _active_sprints(
        self, projects: list[dict[str, Any]], today: date
    ) -> list[ActiveSprintSummary]:
        by_id = {project["_id"]: project for project in projects}
        sprints = self.sprints.search(
            {"projectId": {"$in": list(by_id)}, "status": SprintStatus.ACTIVE.value},
            sort=[("endDate", 1), ("_id", 1)],
            skip=0,
            limit=0,
        )
        totals = IssueRepository(self.db).sprint_totals([sprint["_id"] for sprint in sprints])
        result = []
        for sprint in sprints:
            project = by_id[sprint["projectId"]]
            total = totals.get(sprint["_id"], {})
            points = float(total.get("storyPoints", 0))
            completed = float(total.get("completedStoryPoints", 0))
            end = sprint["endDate"].date()
            result.append(
                ActiveSprintSummary(
                    sprint_id=str(sprint["_id"]),
                    project_id=str(project["_id"]),
                    project_key=project["key"],
                    project_name=project["name"],
                    name=sprint["name"],
                    goal=sprint.get("goal") or "",
                    start_date=sprint["startDate"].date(),
                    end_date=end,
                    remaining_days=max(0, (end - today).days),
                    issue_count=total.get("issueCount", 0),
                    completed_issue_count=total.get("completedIssueCount", 0),
                    story_points=_round(points),
                    completed_story_points=_round(completed),
                    progress_percent=round(completed / points * 100, 1) if points > 0 else None,
                )
            )
        return result

    def _alerts(self, base: dict[str, Any], now: datetime) -> list[AlertGroup]:
        open_issues = {**base, "status": NOT_DONE}
        definitions = [
            (
                "blocked",
                {
                    **open_issues,
                    "blocked": True,
                    "blockedAt": {"$lte": now - timedelta(days=BLOCKED_ALERT_DAYS)},
                },
                "blockedAt",
            ),
            (
                "stale",
                {**open_issues, "updatedAt": {"$lte": now - timedelta(days=STALE_ALERT_DAYS)}},
                "updatedAt",
            ),
            (
                "unassigned_critical_bugs",
                {**_critical_bugs(base), "assigneeId": None},
                "createdAt",
            ),
        ]
        groups = []
        for kind, query, since_field in definitions:
            issues = self.analytics.find_issues(
                query,
                projection=_ISSUE_REF_PROJECTION,
                sort=[(since_field, 1), ("_id", 1)],
                limit=ALERT_ISSUE_LIMIT,
            )
            groups.append(
                AlertGroup(
                    kind=kind,
                    label=ALERT_LABELS[kind],
                    total=self.analytics.count_issues(query),
                    issues=self._issue_refs(issues, since_field, now),
                )
            )
        return groups

    def _my_work(self, user: User, base: dict[str, Any], now: datetime) -> MyWork:
        query = {**base, "assigneeId": user.id, "status": NOT_DONE}
        by_status = self.analytics.status_breakdown(query)
        issues = self.analytics.find_issues(
            query,
            projection=_ISSUE_REF_PROJECTION,
            sort=[("priorityRank", -1), ("updatedAt", -1), ("_id", 1)],
            limit=MY_WORK_LIMIT,
        )
        return MyWork(
            open_count=sum(int(row["count"]) for row in by_status.values()),
            in_progress_count=sum(
                int(by_status.get(status.value, {}).get("count", 0))
                for status in IN_PROGRESS_STATUSES
            ),
            blocked_count=sum(int(row["blocked"]) for row in by_status.values()),
            issues=self._issue_refs(issues, "updatedAt", now),
        )


class ProjectMetricsService(_AnalyticsService):
    def metrics(
        self,
        user: User,
        project_id: ObjectId,
        *,
        sprint_id: ObjectId | None,
        issue_type: IssueType | None,
        first: date | None,
        last: date | None,
    ) -> ProjectMetrics:
        now = datetime.now(UTC)
        project = self._get_project(user, project_id)
        try:
            period = resolve_period(first, last, now.date())
        except AnalyticsRuleError as error:
            raise BusinessRuleError(str(error), field=error.field) from error
        sprint = self._sprint(project_id, sprint_id)

        query: dict[str, Any] = {"projectId": project_id}
        if sprint is not None:
            query["sprintId"] = sprint["_id"]
        if issue_type is not None:
            query["type"] = issue_type.value
        start, end = _midnight(period.first), _midnight(period.last + timedelta(days=1))
        kpis, breakdown = self._kpis(query, [project_id], start, end)
        done = self.analytics.find_issues(
            {**query, "status": DONE, "completedAt": {"$gte": start, "$lt": end}},
            projection={"createdAt": 1, "completedAt": 1},
        )
        lead_time, cycle_time = self._flow_times(done)

        return ProjectMetrics(
            project_id=str(project["_id"]),
            filters=MetricsFilters(
                sprint_id=str(sprint["_id"]) if sprint else None,
                type=issue_type,
                from_date=period.first,
                to_date=period.last,
            ),
            kpis=kpis,
            status_breakdown=breakdown,
            velocity=self._velocity(project_id, sprint, start, end),
            lead_time=lead_time,
            cycle_time=cycle_time,
            aging=self._aging(query, now),
            bug_severity=self._bug_severity(query),
            qa=self._qa(project_id, start, end),
            releases=self._releases(project_id),
            workload=self._workload(query),
            trend=[
                _trend_point(snapshot["day"], snapshot.get("kpis", {}))
                for snapshot in self.snapshots.find_range(project_id, start, _midnight(period.last))
            ],
            sprints=[
                SprintOption(id=str(item["_id"]), name=item["name"], status=item["status"])
                for item in self.sprints.search(
                    {"projectId": project_id}, sort=[("startDate", -1)], skip=0, limit=0
                )
            ],
            generated_at=now,
        )

    def _sprint(self, project_id: ObjectId, sprint_id: ObjectId | None) -> dict[str, Any] | None:
        if sprint_id is None:
            return None
        sprint = self.sprints.find_by_id(sprint_id)
        if sprint is None or sprint["projectId"] != project_id:
            raise BusinessRuleError("O sprint não pertence ao projeto", field="sprintId")
        return sprint

    def _velocity(
        self,
        project_id: ObjectId,
        sprint: dict[str, Any] | None,
        start: datetime,
        end: datetime,
    ) -> VelocityMetric:
        if sprint is not None:
            closed = [sprint] if sprint["status"] == SprintStatus.CLOSED.value else []
        else:
            closed = list(
                reversed(
                    self.sprints.search(
                        {
                            "projectId": project_id,
                            "status": SprintStatus.CLOSED.value,
                            "closedAt": {"$gte": start, "$lt": end},
                        },
                        sort=[("closedAt", -1), ("_id", -1)],
                        skip=0,
                        limit=VELOCITY_SPRINT_LIMIT,
                    )
                )
            )
        entries = [velocity_entry(item) for item in closed]
        predictability = [
            entry.predictability_percent
            for entry in entries
            if entry.predictability_percent is not None
        ]
        return VelocityMetric(
            sprints=entries,
            average_velocity=(
                _round(sum(entry.completed_story_points for entry in entries) / len(entries))
                if entries
                else None
            ),
            average_predictability_percent=(
                round(sum(predictability) / len(predictability), 1) if predictability else None
            ),
        )

    def _flow_times(self, done: list[dict[str, Any]]) -> tuple[DurationMetric, DurationMetric]:
        started = self.analytics.work_started([issue["_id"] for issue in done])
        lead = [_days_between(issue["createdAt"], issue["completedAt"]) for issue in done]
        cycle = []
        for issue in done:
            begin = started.get(issue["_id"])
            if begin is not None and _aware(begin) <= _aware(issue["completedAt"]):
                cycle.append(_days_between(begin, issue["completedAt"]))
        return (
            DurationMetric.model_validate(duration_stats(lead), from_attributes=True),
            DurationMetric.model_validate(duration_stats(cycle), from_attributes=True),
        )

    def _aging(self, query: dict[str, Any], now: datetime) -> AgingMetric:
        open_query = {**query, "status": NOT_DONE}
        counts = [0] * len(AGING_BUCKETS)
        for issue in self.analytics.find_issues(open_query, projection={"createdAt": 1}):
            counts[aging_bucket(int(_days_between(issue["createdAt"], now)))] += 1
        oldest = self.analytics.find_issues(
            open_query,
            projection=_ISSUE_REF_PROJECTION,
            sort=[("createdAt", 1), ("_id", 1)],
            limit=OLDEST_ISSUE_LIMIT,
        )
        return AgingMetric(
            buckets=[
                AgingBucket(label=label, min_days=low, max_days=high, count=counts[index])
                for index, (label, low, high) in enumerate(AGING_BUCKETS)
            ],
            oldest=self._issue_refs(oldest, "createdAt", now),
        )

    def _bug_severity(self, query: dict[str, Any]) -> list[BugSeverityRow]:
        bugs = self.analytics.find_issues(
            {**query, "type": IssueType.BUG.value}, projection={"priority": 1, "status": 1}
        )
        rows = []
        for priority in reversed(list(Priority)):
            matching = [bug for bug in bugs if bug["priority"] == priority.value]
            done = sum(1 for bug in matching if bug["status"] == DONE)
            rows.append(
                BugSeverityRow(
                    priority=priority,
                    open=len(matching) - done,
                    done=done,
                    total=len(matching),
                )
            )
        return rows

    def _qa(self, project_id: ObjectId, start: datetime, end: datetime) -> QaMetric:
        found = self.analytics.test_run_counts([project_id], start, end)
        counts = {result.value: found.get(result.value, 0) for result in TestRunResult}
        return QaMetric(run_count=sum(counts.values()), counts=counts, pass_rate=pass_rate(counts))

    def _releases(self, project_id: ObjectId) -> list[ReleaseQualityRow]:
        releases = ReleaseRepository(self.db).search(
            {"projectId": project_id},
            sort=[("createdAt", -1), ("_id", -1)],
            skip=0,
            limit=RELEASE_LIMIT,
        )
        service = ReleaseService(self.db)
        rows = []
        for release in releases:
            quality = service.quality_for(release)
            rows.append(
                ReleaseQualityRow(
                    release_id=str(release["_id"]),
                    name=release["name"],
                    status=release["status"],
                    planned_date=datetime_to_date(release.get("plannedDate")),
                    released_at=release.get("releasedAt"),
                    issue_count=quality.issues.total,
                    done_issue_count=quality.issues.done,
                    known_bug_count=quality.known_bugs.total,
                    open_bug_count=quality.known_bugs.open,
                    open_critical_bug_count=quality.known_bugs.open_critical,
                    test_pass_rate=quality.tests.pass_rate,
                    ready=quality.ready,
                )
            )
        return rows

    def _workload(self, query: dict[str, Any]) -> list[WorkloadRow]:
        issues = self.analytics.find_issues(
            {**query, "status": NOT_DONE},
            projection={"assigneeId": 1, "status": 1, "blocked": 1, "storyPoints": 1},
        )
        groups: dict[ObjectId | None, list[dict[str, Any]]] = defaultdict(list)
        for issue in issues:
            groups[issue.get("assigneeId")].append(issue)
        users = self._user_summaries(groups)
        in_progress = {status.value for status in IN_PROGRESS_STATUSES}
        rows = [
            WorkloadRow(
                assignee=users.get(assignee_id) if assignee_id else None,
                open_count=len(items),
                in_progress_count=sum(1 for item in items if item["status"] in in_progress),
                blocked_count=sum(1 for item in items if item.get("blocked")),
                open_story_points=_round(sum(item.get("storyPoints") or 0 for item in items)),
            )
            for assignee_id, items in groups.items()
        ]
        return sorted(
            rows,
            key=lambda row: (
                row.assignee is None,
                row.assignee.name.lower() if row.assignee else "",
            ),
        )


class ReportSnapshotService(_AnalyticsService):
    def create(self, user: User, project_id: ObjectId) -> ReportSnapshot:
        project = dict(ensure_project_manager(user, self.projects.find_by_id(project_id)))
        if is_archived(project):
            raise BusinessRuleError("O projeto está arquivado e só pode ser consultado")
        return self.capture(project)

    def capture(self, project: dict[str, Any]) -> ReportSnapshot:
        """Grava (ou substitui) o snapshot de hoje com os KPIs atuais do projeto."""
        now = datetime.now(UTC)
        since = _midnight(now.date() - timedelta(days=PASS_RATE_WINDOW_DAYS - 1))
        kpis, breakdown = self._kpis({"projectId": project["_id"]}, [project["_id"]], since)
        snapshot = ReportSnapshot(
            project_id=str(project["_id"]),
            day=now.date(),
            kpis=kpis,
            status_breakdown=breakdown,
            taken_at=now,
        )
        self.snapshots.save(
            {
                "projectId": project["_id"],
                "day": _midnight(now.date()),
                "kpis": kpis.model_dump(by_alias=True, mode="json"),
                "statusBreakdown": [
                    item.model_dump(by_alias=True, mode="json") for item in breakdown
                ],
                "takenAt": now,
            }
        )
        return snapshot

    def capture_all(self) -> tuple[int, int]:
        """Snapshot de todos os projetos não arquivados; devolve (gravados, falhados)."""
        saved = failed = 0
        projects = self.projects.search(
            {"status": {"$ne": ProjectStatus.ARCHIVED.value}},
            sort=[("_id", 1)],
            skip=0,
            limit=0,
        )
        for project in projects:
            try:
                self.capture(project)
                saved += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Falha no snapshot de relatório", extra={"projectId": str(project["_id"])}
                )
        return saved, failed
