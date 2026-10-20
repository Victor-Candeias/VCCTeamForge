from fastapi import FastAPI

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    docs_enabled = bool(settings.api_docs_enabled)

    app = FastAPI(
        title="VCCTeamForge API",
        version=__version__,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
