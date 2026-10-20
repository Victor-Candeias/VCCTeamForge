import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]

ENV_FILE_VARIABLE = "VCCTF_ENV_FILE"

# backend/app/core/config.py -> raiz do repositório
DEFAULT_DATABASE_DIR = Path(__file__).resolve().parents[3] / "database"


class Settings(BaseSettings):
    """Configuração da API, lida de variáveis de ambiente e (opcionalmente) de um ficheiro .env.

    Prioridade: argumentos explícitos > variáveis de ambiente > ficheiro .env > valores por omissão.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    app_env: Environment = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=5000, ge=1, le=65535)
    app_workers: int = Field(default=1, ge=1, le=8)
    forwarded_allow_ips: str = "127.0.0.1"
    api_docs_enabled: bool | None = None

    mongodb_host: str = "127.0.0.1"
    mongodb_port: int = Field(default=27017, ge=1, le=65535)
    mongodb_database: str = "VCCTeamForgeDB"
    mongodb_username: str | None = None
    mongodb_password: SecretStr | None = None
    mongodb_auth_source: str | None = None
    mongodb_server_selection_timeout_ms: int = Field(default=5000, ge=100)
    mongodb_max_pool_size: int = Field(default=20, ge=1, le=200)

    database_dir: Path = DEFAULT_DATABASE_DIR

    attachments_path: Path = Path("var/attachments")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    log_file: Path | None = None
    log_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    log_backup_count: int = Field(default=5, ge=0, le=100)

    health_min_free_disk_mb: int = Field(default=1024, ge=0)

    @model_validator(mode="after")
    def _apply_environment_rules(self) -> "Settings":
        if self.api_docs_enabled is None:
            self.api_docs_enabled = self.app_env != "production"
        if self.mongodb_username and not self.mongodb_auth_source:
            self.mongodb_auth_source = self.mongodb_database
        if bool(self.mongodb_username) != bool(self.mongodb_password):
            raise ValueError("MONGODB_USERNAME e MONGODB_PASSWORD têm de ser definidos em conjunto")
        if self.is_production:
            self._validate_production()
        return self

    def _validate_production(self) -> None:
        errors = []
        if not self.mongodb_username:
            errors.append("MONGODB_USERNAME/MONGODB_PASSWORD são obrigatórios em produção")
        if not self.attachments_path.is_absolute():
            errors.append("ATTACHMENTS_PATH tem de ser um caminho absoluto em produção")
        if errors:
            raise ValueError("; ".join(errors))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def load_settings(env_file: str | os.PathLike[str] | None = None) -> Settings:
    if env_file is None:
        env_file = os.environ.get(ENV_FILE_VARIABLE, ".env")
    return Settings(_env_file=env_file)  # type: ignore[call-arg]


@lru_cache
def get_settings() -> Settings:
    return load_settings()
