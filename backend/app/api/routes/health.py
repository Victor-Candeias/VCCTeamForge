from fastapi import APIRouter, Depends, Request, Response

from app import __version__
from app.api.deps import get_app_settings
from app.core.config import Settings
from app.schemas.health import HealthResponse, ReadinessResponse
from app.services import health as health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    """O processo está a responder (não verifica dependências)."""
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready(
    request: Request, response: Response, settings: Settings = Depends(get_app_settings)
) -> ReadinessResponse:
    """Dependências disponíveis: 503 se o MongoDB falhar; ``degraded`` se o disco estiver baixo."""
    checks = {
        "mongodb": health_service.check_mongodb(request.app.state.mongo_client),
        "disk": health_service.check_disk(settings),
    }
    status = health_service.overall_status(checks)
    if status == "error":
        response.status_code = 503
    return ReadinessResponse(status=status, version=__version__, checks=checks)
