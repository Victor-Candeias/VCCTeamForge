import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.logging import JsonFormatter, RequestIdFilter, configure_logging, request_id_var


@pytest.fixture(autouse=True)
def _restore_logging():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


def test_json_formatter_includes_request_id_and_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"name": "app.request", "levelname": "INFO", "msg": "GET %s", "args": ("/api",)}
    )
    record.status = 200
    token = request_id_var.set("req-1")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "GET /api"
    assert payload["requestId"] == "req-1"
    assert payload["status"] == 200
    assert payload["time"].endswith("+00:00")


def test_file_logging_uses_rotation(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "api.log"
    configure_logging(
        Settings(log_file=log_file, log_format="json", log_max_bytes=2048, log_backup_count=3)
    )

    logging.getLogger("app.test").warning("rotacao")

    handler = next(h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler))
    assert handler.maxBytes == 2048
    assert handler.backupCount == 3
    handler.flush()
    assert json.loads(log_file.read_text().splitlines()[-1])["message"] == "rotacao"
