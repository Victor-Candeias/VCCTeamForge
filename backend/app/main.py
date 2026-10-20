from fastapi import FastAPI

from app import __version__
from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="VCCTeamForge API",
        version=__version__,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
