from fastapi import APIRouter, Depends, Query, Response
from pymongo.database import Database

from app.api.deps import get_db, parse_object_id, require_permissions
from app.domain.permissions import Permission
from app.domain.users import User
from app.schemas.analytics import DashboardOverview
from app.services.analytics import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

can_read_reports = require_permissions(Permission.REPORTS_READ)


@router.get("/overview", response_model=DashboardOverview)
def get_overview(
    response: Response,
    project_id: str | None = Query(default=None, alias="projectId"),
    user: User = Depends(can_read_reports),
    db: Database = Depends(get_db),
) -> DashboardOverview:
    response.headers["Cache-Control"] = "no-store"
    parsed = parse_object_id(project_id, "Projeto") if project_id else None
    return DashboardService(db).overview(user, parsed)
