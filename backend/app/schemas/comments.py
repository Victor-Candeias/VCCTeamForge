from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.auth import UserSummary
from app.schemas.base import ApiModel

COMMENT_MAX_LENGTH = 10_000


class CommentInput(ApiModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=COMMENT_MAX_LENGTH)


class Comment(ApiModel):
    id: str
    issue_id: str
    author: UserSummary | None
    body: str | None
    deleted: bool
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    can_edit: bool
    can_delete: bool
