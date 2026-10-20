import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.repositories import mongo

logger = logging.getLogger(__name__)


def _connect_database(settings: Settings) -> MongoClient:
    client = mongo.create_client(settings)
    try:
        info = mongo.check_server_compatibility(client)
    except PyMongoError as error:
        # A API arranca na mesma; o health check de readiness reporta a indisponibilidade.
        logger.warning("MongoDB indisponível no arranque: %s", error)
    else:
        logger.info("MongoDB %s ligado (base de dados %s)", info.version, settings.mongodb_database)
    return client


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    owns_client = app.state.mongo_client is None
    if owns_client:
        app.state.mongo_client = _connect_database(settings)
    app.state.db = mongo.get_database(app.state.mongo_client, settings)
    try:
        yield
    finally:
        if owns_client:
            app.state.mongo_client.close()
            app.state.mongo_client = None


def create_app(
    settings: Settings | None = None, mongo_client: MongoClient | None = None
) -> FastAPI:
    """Cria a aplicação. ``mongo_client`` permite injetar um cliente (testes); não é fechado."""
    settings = settings or get_settings()
    docs_enabled = bool(settings.api_docs_enabled)

    app = FastAPI(
        title="VCCTeamForge API",
        version=__version__,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.mongo_client = mongo_client
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
