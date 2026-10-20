from typing import Literal

from app.schemas.base import ApiModel

Status = Literal["ok", "degraded", "error"]


class HealthResponse(ApiModel):
    status: Status
    version: str


class CheckResult(ApiModel):
    status: Status
    latency_ms: float | None = None
    detail: str | None = None


class ReadinessResponse(HealthResponse):
    checks: dict[str, CheckResult]
