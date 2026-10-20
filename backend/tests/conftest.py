import os
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core import security
from app.core.config import DEFAULT_DATABASE_DIR, Settings
from app.domain.permissions import Role
from app.domain.users import User, UserStatus
from app.main import create_app
from app.maintenance import indexes
from app.repositories import mongo
from app.repositories.users import UserRepository


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


# --- API autenticada (projetos, issues, ...) --------------------------------------------------

API_PASSWORD = "uma-password-segura"


@cache
def _api_password_hash() -> str:
    return security.hash_password(API_PASSWORD)


class ApiClient:
    """Cliente de testes com sessão iniciada e cabeçalho CSRF automático."""

    def __init__(self, client: TestClient, user: User) -> None:
        self.client = client
        self.user = user

    def _headers(self, method: str) -> dict[str, str]:
        if method in {"GET", "HEAD", "OPTIONS"}:
            return {}
        return {"X-CSRF-Token": self.client.cookies.get("vcctf_csrf", "")}

    def request(self, method: str, path: str, **kwargs: Any):
        headers = {**self._headers(method), **kwargs.pop("headers", {})}
        return self.client.request(method, path, headers=headers, **kwargs)

    def get(self, path: str, **kwargs: Any):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any):
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture
def api_settings(mongo_settings: Settings, tmp_path: Path) -> Settings:
    return mongo_settings.model_copy(
        update={"attachments_path": tmp_path / "attachments", "login_max_failures_per_ip": 1000}
    )


@pytest.fixture
def indexed_db(db: Database) -> Database:
    indexes.ensure_indexes(db, indexes.load_index_specs(DEFAULT_DATABASE_DIR))
    return db


@pytest.fixture
def make_user(indexed_db: Database) -> Callable[..., User]:
    repository = UserRepository(indexed_db)

    def factory(name: str, role: Role = Role.DEVELOPER, *, active: bool = True) -> User:
        document = repository.create(
            email=f"{name.lower()}@exemplo.pt",
            name=name,
            role=role,
            password_hash=_api_password_hash(),
            now=datetime.now(UTC),
        )
        if not active:
            indexed_db.users.update_one(
                {"_id": document["_id"]}, {"$set": {"status": UserStatus.DISABLED.value}}
            )
            document["status"] = UserStatus.DISABLED.value
        return User.from_document(document)

    return factory


@pytest.fixture
def api_app(api_settings: Settings, mongo_client: MongoClient, indexed_db: Database):
    return create_app(api_settings, mongo_client=mongo_client)


@pytest.fixture
def login_as(api_app) -> Iterator[Callable[[User], ApiClient]]:
    """Abre um cliente com sessão iniciada para o utilizador indicado."""
    clients: list[TestClient] = []

    def factory(user: User) -> ApiClient:
        client = TestClient(api_app)
        client.__enter__()
        clients.append(client)
        csrf = client.get("/api/auth/csrf").json()["csrfToken"]
        response = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": API_PASSWORD},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200, response.text
        return ApiClient(client, user)

    yield factory
    for client in clients:
        client.__exit__(None, None, None)
