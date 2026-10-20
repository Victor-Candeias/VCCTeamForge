"""Logging da aplicação: texto (desenvolvimento) ou JSON (produção), com request id."""

import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime

from app.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "request_id",
    "color_message",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", "-")
        payload = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "requestId": None if request_id == "-" else request_id,
        }
        payload.update(
            {key: value for key, value in record.__dict__.items() if key not in _RESERVED}
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


TEXT_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"


def build_logging_config(settings: Settings) -> dict:
    formatter = {"()": JsonFormatter} if settings.log_format == "json" else {"format": TEXT_FORMAT}
    handlers: dict[str, dict] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["request_id"],
        }
    }
    if settings.log_file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filters": ["request_id"],
            "filename": str(settings.log_file),
            "maxBytes": settings.log_max_bytes,
            "backupCount": settings.log_backup_count,
            "encoding": "utf-8",
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"request_id": {"()": RequestIdFilter}},
        "formatters": {"default": formatter},
        "handlers": handlers,
        "root": {"level": settings.log_level, "handlers": list(handlers)},
        "loggers": {
            # Os pedidos são registados pelo middleware da aplicação (com request id).
            "uvicorn.access": {"level": "WARNING", "propagate": False},
            "uvicorn": {"level": settings.log_level, "handlers": [], "propagate": True},
            "uvicorn.error": {"level": settings.log_level, "handlers": [], "propagate": True},
            "pymongo": {"level": "WARNING"},
        },
    }


def configure_logging(settings: Settings) -> None:
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(build_logging_config(settings))
