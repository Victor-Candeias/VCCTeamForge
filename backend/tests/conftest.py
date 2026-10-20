import os
import uuid
from collections.abc import Iterator

import pytest
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.repositories import mongo


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(f"VCCTF_TEST_MONGODB_{name}", default)


@pytest.fixture(scope="session")
def mongo_settings() -> Settings:
    """Settings para testes de integração (BD descartável, nunca a de produção)."""
    return Settings(
        app_env="test",
        mongodb_host=_env("HOST", "127.0.0.1"),
        mongodb_port=int(_env("PORT", "27017")),
        mongodb_username=_env("USERNAME"),
        mongodb_password=_env("PASSWORD"),
        mongodb_auth_source=_env("AUTH_SOURCE"),
        mongodb_database=_env("DATABASE", f"VCCTeamForgeDB_test_{uuid.uuid4().hex[:8]}"),
        mongodb_server_selection_timeout_ms=2000,
    )


@pytest.fixture(scope="session")
def mongo_client(mongo_settings: Settings) -> Iterator[MongoClient]:
    client = mongo.create_client(mongo_settings)
    try:
        # "ping" não exige autenticação; listCollections confirma também as permissões.
        mongo.get_database(client, mongo_settings).list_collection_names()
    except PyMongoError as error:
        client.close()
        message = f"MongoDB de teste indisponível: {error}"
        if os.environ.get("VCCTF_REQUIRE_MONGO") == "1":
            pytest.fail(message)
        pytest.skip(message)
    yield client
    client.drop_database(mongo_settings.mongodb_database)
    client.close()


@pytest.fixture
def db(mongo_client: MongoClient, mongo_settings: Settings) -> Iterator[Database]:
    database = mongo.get_database(mongo_client, mongo_settings)
    yield database
    for name in database.list_collection_names():
        database.drop_collection(name)
