import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.core.errors import NotFoundError, TooManyRequestsError
from app.main import create_app


class Credentials(BaseModel):
    email: str
    password: str


def _app_with_failing_routes() -> FastAPI:
    router = APIRouter()

    @router.get("/missing")
    def missing() -> None:
        raise NotFoundError("Projeto DVC não existe", resource="project")

    @router.get("/throttled")
    def throttled() -> None:
        raise TooManyRequestsError(retry_after=60)

    @router.get("/boom")
    def boom() -> None:
        raise RuntimeError("segredo interno")

    @router.get("/db-down")
    def db_down() -> None:
        raise ServerSelectionTimeoutError("127.0.0.1:27017 timeout")

    @router.post("/login")
    def login(credentials: Credentials) -> None:
        return None

    app = create_app(Settings())
    app.include_router(router, prefix="/api/test")
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app_with_failing_routes())


def _assert_problem(response, status: int) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == status
    assert body["requestId"] == response.headers["x-request-id"]
    return body


def test_app_error_is_rendered_as_problem(client: TestClient) -> None:
    body = _assert_problem(client.get("/api/test/missing"), 404)

    assert body["title"] == "Recurso não encontrado"
    assert body["detail"] == "Projeto DVC não existe"
    assert body["instance"] == "/api/test/missing"
    assert body["resource"] == "project"


def test_unknown_route_is_problem(client: TestClient) -> None:
    body = _assert_problem(client.get("/api/does-not-exist"), 404)

    assert body["title"] == "Not Found"


def test_too_many_requests_sets_retry_after(client: TestClient) -> None:
    response = client.get("/api/test/throttled")

    _assert_problem(response, 429)
    assert response.headers["retry-after"] == "60"


def test_validation_error_does_not_echo_input(client: TestClient) -> None:
    response = client.post("/api/test/login", json={"email": "a@b.pt", "password": 123})

    body = _assert_problem(response, 422)
    assert body["errors"][0]["loc"] == ["body", "password"]
    assert "123" not in response.text


def test_unhandled_error_hides_internal_details(client: TestClient) -> None:
    response = client.get("/api/test/boom")

    body = _assert_problem(response, 500)
    assert body["title"] == "Erro interno"
    assert "segredo" not in response.text


def test_database_unavailable_returns_503(client: TestClient) -> None:
    body = _assert_problem(client.get("/api/test/db-down"), 503)

    assert "27017" not in body["detail"]


def test_valid_incoming_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/api/test/missing", headers={"X-Request-ID": "nginx-abc.123"})

    assert response.headers["x-request-id"] == "nginx-abc.123"
    assert response.json()["requestId"] == "nginx-abc.123"


def test_invalid_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "bad id\twith spaces"})

    assert response.headers["x-request-id"] != "bad id\twith spaces"
    assert len(response.headers["x-request-id"]) == 32
