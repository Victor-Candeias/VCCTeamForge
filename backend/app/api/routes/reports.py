from fastapi import APIRouter, Depends, Response
from pymongo.database import Database

from app.api.deps import get_db, parse_object_id, require_permissions
from app.domain.permissions import Permission
from app.domain.users import User
from app.schemas.reports import SprintReport
from app.services.sprint_reports import SprintReportService

router = APIRouter(prefix="/reports", tags=["reports"])

can_read_reports = require_permissions(Permission.REPORTS_READ)


@router.get("/sprints/{sprint_id}", response_model=SprintReport)
def get_sprint_report(
    sprint_id: str,
    response: Response,
    user: User = Depends(can_read_reports),
    db: Database = Depends(get_db),
) -> SprintReport:
    response.headers["Cache-Control"] = "no-store"
    return SprintReportService(db).report(user, parse_object_id(sprint_id, "Sprint"))
