from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import ENV_FILE_VARIABLE, Settings, load_settings
from app.main import create_app

PRODUCTION = {
    "app_env": "production",
    "mongodb_username": "app",
    "mongodb_password": "secret",
    "attachments_path": Path("/var/lib/vccteamforge/attachments"),
}


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(Settings.model_fields) + [ENV_FILE_VARIABLE]:
        monkeypatch.delenv(name.upper(), raising=False)


def test_environment_variables_override_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "api.env"
    env_file.write_text("APP_PORT=5100\nMONGODB_DATABASE=FromFile\nMONGODB_USERNAME=\n")
    monkeypatch.setenv("MONGODB_DATABASE", "FromEnv")
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(env_file))

    settings = load_settings()

    assert settings.app_port == 5100
    assert settings.mongodb_database == "FromEnv"
    assert settings.mongodb_username is None


def test_explicit_env_file_must_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(tmp_path / "missing.env"))

    with pytest.raises(FileNotFoundError, match=ENV_FILE_VARIABLE):
        load_settings()


def test_auth_source_defaults_to_database() -> None:
    settings = Settings(mongodb_database="Db", mongodb_username="u", mongodb_password="p")

    assert settings.mongodb_auth_source == "Db"


def test_username_requires_password() -> None:
    with pytest.raises(ValidationError, match="MONGODB_PASSWORD"):
        Settings(mongodb_username="u")


def test_production_requires_credentials_and_absolute_attachments_path() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(app_env="production", attachments_path=Path("relative"))

    message = str(error.value)
    assert "MONGODB_USERNAME" in message
    assert "ATTACHMENTS_PATH" in message


@pytest.mark.parametrize(
    ("overrides", "docs_status"),
    [({}, 200), (PRODUCTION, 404), ({**PRODUCTION, "api_docs_enabled": True}, 200)],
)
def test_api_docs_follow_environment(overrides: dict, docs_status: int) -> None:
    client = TestClient(create_app(Settings(**overrides)))

    assert client.get("/api/openapi.json").status_code == docs_status
    assert client.get("/api/docs").status_code == docs_status
