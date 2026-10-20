from pathlib import Path

from fastapi.testclient import TestClient
from pymongo import MongoClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


def test_liveness_does_not_depend_on_database() -> None:
    client = TestClient(create_app(Settings()))

    for path in ("/api/health", "/api/health/live"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": __version__}


def test_readiness_ok_with_database(
    mongo_client: MongoClient, mongo_settings: Settings, tmp_path: Path
) -> None:
    settings = mongo_settings.model_copy(
        update={"attachments_path": tmp_path, "health_min_free_disk_mb": 0}
    )

    with TestClient(create_app(settings, mongo_client=mongo_client)) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["mongodb"]["status"] == "ok"
    assert body["checks"]["mongodb"]["latencyMs"] >= 0
    assert body["checks"]["disk"]["status"] == "ok"


def test_readiness_fails_when_database_is_unreachable(tmp_path: Path) -> None:
    settings = Settings(
        mongodb_port=1,
        mongodb_server_selection_timeout_ms=200,
        attachments_path=tmp_path / "missing" / "dir",
        health_min_free_disk_mb=0,
    )
    unreachable = MongoClient(port=1, serverSelectionTimeoutMS=200, connect=False)

    with TestClient(create_app(settings, mongo_client=unreachable)) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["mongodb"] == {
        "status": "error",
        "latencyMs": None,
        "detail": "MongoDB indisponível",
    }
    unreachable.close()


def test_readiness_degraded_when_disk_is_low(
    mongo_client: MongoClient, mongo_settings: Settings, tmp_path: Path
) -> None:
    settings = mongo_settings.model_copy(
        update={"attachments_path": tmp_path, "health_min_free_disk_mb": 10**12}
    )

    with TestClient(create_app(settings, mongo_client=mongo_client)) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["disk"]["status"] == "degraded"
