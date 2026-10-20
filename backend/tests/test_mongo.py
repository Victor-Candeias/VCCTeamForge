from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.main import create_app
from app.repositories import mongo


def _client_reporting(version: str, version_array: list[int] | None = None) -> MagicMock:
    client = MagicMock()
    build_info = {"version": version}
    if version_array is not None:
        build_info["versionArray"] = version_array
    client.admin.command.return_value = build_info
    return client


@pytest.mark.parametrize(
    ("version", "version_array"),
    [("4.4.29", [4, 4, 29, 0]), ("5.0.0", None), ("4.4.0-rc1", None)],
)
def test_supported_server_versions(version: str, version_array: list[int] | None) -> None:
    info = mongo.check_server_compatibility(_client_reporting(version, version_array))

    assert info.version == version


def test_older_server_is_rejected() -> None:
    with pytest.raises(mongo.IncompatibleServerError, match="4.2.24"):
        mongo.check_server_compatibility(_client_reporting("4.2.24", [4, 2, 24, 0]))


def test_client_uses_settings_without_connecting() -> None:
    settings = Settings(
        mongodb_host="db.local",
        mongodb_port=27018,
        mongodb_username="app",
        mongodb_password="secret",
        mongodb_max_pool_size=7,
        mongodb_server_selection_timeout_ms=1500,
    )

    client = mongo.create_client(settings)
    try:
        assert client.options.pool_options.max_pool_size == 7
        assert client.options.server_selection_timeout == 1.5
        assert client.codec_options.tz_aware is True
        assert client.options.pool_options._credentials.source == "VCCTeamForgeDB"
    finally:
        client.close()


def test_app_starts_when_mongodb_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(_client):
        raise ServerSelectionTimeoutError("down")

    monkeypatch.setattr(mongo, "check_server_compatibility", unavailable)

    with TestClient(create_app(Settings())) as client:
        assert client.get("/api/health").status_code == 200
        assert client.app.state.db.name == "VCCTeamForgeDB"
