from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel


class FieldChange(ApiModel):
    field: str
    from_value: Any = Field(default=None, alias="from")
    to_value: Any = Field(default=None, alias="to")


class HistoryEvent(ApiModel):
    id: str
    type: str
    actor: UserSummary | None
    changes: list[FieldChange]
    details: dict[str, Any]
    created_at: datetime
