from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pymongo.database import Database

from app.api.deps import client_ip, get_db, parse_object_id, require_permissions
from app.domain.exports import ExportFormat
from app.domain.issues import IssueType
from app.domain.permissions import Permission
from app.domain.users import User
from app.schemas.analytics import ProjectMetrics, ReportSnapshot
from app.schemas.reports import SprintReport
from app.services.analytics import ProjectMetricsService, ReportSnapshotService
from app.services.common import object_id_or_422
from app.services.report_exports import ReportExportService
from app.services.sprint_reports import SprintReportService

router = APIRouter(prefix="/reports", tags=["reports"])

can_read_reports = require_permissions(Permission.REPORTS_READ)
can_manage_projects = require_permissions(Permission.PROJECTS_MANAGE)


@router.get("/sprints/{sprint_id}", response_model=SprintReport)
def get_sprint_report(
    sprint_id: str,
    response: Response,
    user: User = Depends(can_read_reports),
    db: Database = Depends(get_db),
) -> SprintReport:
    response.headers["Cache-Control"] = "no-store"
    return SprintReportService(db).report(user, parse_object_id(sprint_id, "Sprint"))


@router.get("/projects/{project_id}/metrics", response_model=ProjectMetrics)
def get_project_metrics(
    project_id: str,
    response: Response,
    sprint_id: str | None = Query(default=None, alias="sprintId"),
    issue_type: IssueType | None = Query(default=None, alias="type"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(can_read_reports),
    db: Database = Depends(get_db),
) -> ProjectMetrics:
    response.headers["Cache-Control"] = "no-store"
    return ProjectMetricsService(db).metrics(
        user,
        parse_object_id(project_id, "Projeto"),
        sprint_id=object_id_or_422(sprint_id, "sprintId") if sprint_id else None,
        issue_type=issue_type,
        first=date_from,
        last=date_to,
    )


@router.post(
    "/projects/{project_id}/snapshots",
    response_model=ReportSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_report_snapshot(
    project_id: str,
    user: User = Depends(can_manage_projects),
    db: Database = Depends(get_db),
) -> ReportSnapshot:
    return ReportSnapshotService(db).create(user, parse_object_id(project_id, "Projeto"))


@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {
            "description": "Ficheiro CSV, XLSX ou PDF",
            "content": {"text/csv": {}, "application/pdf": {}},
        }
    },
)
def export_report(
    request: Request,
    project_id: str = Query(alias="projectId"),
    export_format: ExportFormat = Query(alias="format"),
    sprint_id: str | None = Query(default=None, alias="sprintId"),
    issue_type: IssueType | None = Query(default=None, alias="type"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(can_read_reports),
    db: Database = Depends(get_db),
) -> Response:
    exported = ReportExportService(db).export(
        user,
        parse_object_id(project_id, "Projeto"),
        export_format,
        sprint_id=object_id_or_422(sprint_id, "sprintId") if sprint_id else None,
        issue_type=issue_type,
        first=date_from,
        last=date_to,
        ip=client_ip(request),
    )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{exported.filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
