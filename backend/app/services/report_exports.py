"""Exportação das métricas de um projeto em CSV, XLSX ou PDF (README §9 "Exportações")."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError
from app.domain.exports import EXPORT_MAX_ISSUES, MEDIA_TYPES, ExportFormat, export_filename
from app.domain.issues import IssueStatus, IssueType
from app.domain.users import User
from app.exports.csv_writer import write_csv
from app.exports.pdf_writer import write_pdf
from app.exports.report import IssueExportRow, ReportData
from app.exports.xlsx_writer import write_xlsx
from app.repositories.analytics import AnalyticsRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.projects import ProjectRepository
from app.repositories.users import UserRepository
from app.schemas.analytics import ProjectMetrics
from app.services.analytics import ProjectMetricsService

logger = logging.getLogger(__name__)

WRITERS = {ExportFormat.CSV: write_csv, ExportFormat.XLSX: write_xlsx, ExportFormat.PDF: write_pdf}
ISSUE_PROJECTION = {
    "key": 1,
    "title": 1,
    "type": 1,
    "status": 1,
    "priority": 1,
    "assigneeId": 1,
    "sprintId": 1,
    "storyPoints": 1,
    "blocked": 1,
    "createdAt": 1,
    "updatedAt": 1,
    "completedAt": 1,
}


@dataclass(frozen=True)
class ExportFile:
    content: bytes
    media_type: str
    filename: str


class ReportExportService:
    def __init__(self, db: Database) -> None:
        self.metrics = ProjectMetricsService(db)
        self.analytics = AnalyticsRepository(db)
        self.projects = ProjectRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditLogRepository(db)

    def export(
        self,
        user: User,
        project_id: ObjectId,
        export_format: ExportFormat,
        *,
        sprint_id: ObjectId | None,
        issue_type: IssueType | None,
        first: date | None,
        last: date | None,
        ip: str | None = None,
    ) -> ExportFile:
        # Valida acesso, período e sprint tal como a página de métricas.
        metrics = self.metrics.metrics(
            user,
            project_id,
            sprint_id=sprint_id,
            issue_type=issue_type,
            first=first,
            last=last,
        )
        project = self.projects.find_by_id(project_id)
        if project is None:  # removido entre as duas leituras
            raise BusinessRuleError("Projeto indisponível")
        query = self._issue_query(project_id, metrics)
        total = self.analytics.count_issues(query)
        if total > EXPORT_MAX_ISSUES:
            raise BusinessRuleError(
                f"A exportação está limitada a {EXPORT_MAX_ISSUES} issues ({total} encontradas); "
                "reduza o período ou filtre por sprint ou tipo"
            )
        sprint_names = {sprint.id: sprint.name for sprint in metrics.sprints}
        data = ReportData(
            project_key=project["key"],
            project_name=project["name"],
            sprint_name=sprint_names.get(metrics.filters.sprint_id or ""),
            generated_by=user.name,
            metrics=metrics,
            issues=self._issues(query, sprint_names),
        )
        content = WRITERS[export_format](data)

        self.audit.record(
            "report.exported",
            now=metrics.generated_at,
            actor_id=user.id,
            entity_type="project",
            entity_id=project_id,
            ip=ip,
            details={
                "projectKey": project["key"],
                "format": export_format.value,
                "filters": metrics.filters.model_dump(mode="json", by_alias=True),
                "issueCount": len(data.issues),
            },
        )
        logger.info(
            "Exportação %s do projeto %s (%d issues)",
            export_format.value,
            project["key"],
            len(data.issues),
        )
        return ExportFile(
            content=content,
            media_type=MEDIA_TYPES[export_format],
            filename=export_filename(project["key"], export_format, metrics.generated_at.date()),
        )

    @staticmethod
    def _issue_query(project_id: ObjectId, metrics: ProjectMetrics) -> dict[str, Any]:
        """Issues do filtro ativas no período: criadas até ao fim e por concluir ou concluídas
        depois do início."""
        filters = metrics.filters
        start = datetime.combine(filters.from_date, time.min, tzinfo=UTC)
        end = datetime.combine(filters.to_date + timedelta(days=1), time.min, tzinfo=UTC)
        query: dict[str, Any] = {
            "projectId": project_id,
            "createdAt": {"$lt": end},
            "$or": [
                {"status": {"$ne": IssueStatus.DONE.value}},
                {"completedAt": {"$gte": start}},
            ],
        }
        if filters.sprint_id:
            query["sprintId"] = ObjectId(filters.sprint_id)
        if filters.type:
            query["type"] = filters.type.value
        return query

    def _issues(self, query: dict[str, Any], sprint_names: dict[str, str]) -> list[IssueExportRow]:
        issues = self.analytics.find_issues(
            query, projection=ISSUE_PROJECTION, sort=[("number", 1), ("_id", 1)]
        )
        assignee_ids = {issue["assigneeId"] for issue in issues if issue.get("assigneeId")}
        users = self.users.find_by_ids(list(assignee_ids))
        return [
            IssueExportRow(
                key=issue["key"],
                title=issue["title"],
                type=issue["type"],
                status=issue["status"],
                priority=issue["priority"],
                assignee=(
                    users[issue["assigneeId"]]["name"] if issue.get("assigneeId") in users else None
                ),
                sprint=sprint_names.get(str(issue["sprintId"])) if issue.get("sprintId") else None,
                story_points=issue.get("storyPoints"),
                blocked=bool(issue.get("blocked")),
                created_at=issue["createdAt"],
                updated_at=issue.get("updatedAt"),
                completed_at=issue.get("completedAt"),
            )
            for issue in issues
        ]
