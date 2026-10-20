from datetime import datetime
from typing import Any

from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel


class AuditLog(ApiModel):
    id: str
    action: str
    actor: UserSummary | None
    entity_type: str | None
    entity_id: str | None
    ip: str | None
    request_id: str | None
    details: dict[str, Any]
    created_at: datetime
