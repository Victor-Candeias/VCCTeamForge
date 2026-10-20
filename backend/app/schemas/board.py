from pydantic import ConfigDict, Field, model_validator

from app.domain.issues import IssueStatus
from app.schemas.base import ApiModel
from app.schemas.issues import IssueSummary


class RankMove(ApiModel):
    """Nova posição: imediatamente antes de ``beforeId`` e/ou depois de ``afterId``."""

    model_config = ConfigDict(extra="forbid")

    before_id: str | None = None
    after_id: str | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def _require_neighbour(self) -> "RankMove":
        if not self.before_id and not self.after_id:
            raise ValueError("Indique beforeId e/ou afterId")
        return self


class BoardColumn(ApiModel):
    status: IssueStatus
    items: list[IssueSummary]
    total: int
    truncated: bool


class Board(ApiModel):
    columns: list[BoardColumn]
    column_limit: int
    done_window_days: int
