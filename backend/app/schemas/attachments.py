from datetime import datetime

from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel


class Attachment(ApiModel):
    id: str
    issue_id: str
    original_name: str
    content_type: str
    size: int
    sha256: str
    is_image: bool
    uploaded_by: UserSummary | None
    created_at: datetime
    can_delete: bool
