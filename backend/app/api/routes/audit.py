from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from pymongo.database import Database

from app.api.deps import get_db, require_permissions
from app.domain.permissions import Permission
from app.domain.users import User
from app.schemas.audit import AuditLog
from app.schemas.common import Page, PageParams
from app.services.audit import AuditService, build_audit_filter

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLog])
def list_audit_logs(
    response: Response,
    entity_type: str | None = Query(default=None, alias="entityType", max_length=50),
    entity_id: str | None = Query(default=None, alias="entityId", max_length=100),
    actor_id: str | None = Query(default=None, alias="actorId", max_length=50),
    action: str | None = Query(default=None, max_length=100),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    page: PageParams = Depends(),
    _: User = Depends(require_permissions(Permission.AUDIT_READ)),
    db: Database = Depends(get_db),
) -> Page[AuditLog]:
    response.headers["Cache-Control"] = "no-store"
    query = build_audit_filter(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
    items, total = AuditService(db).search(query, page)
    return Page[AuditLog](items=items, total=total, page=page.page, page_size=page.page_size)
