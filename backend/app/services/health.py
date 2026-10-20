"""Verificações de saúde: estado do processo e das dependências."""

import logging
import shutil
import time
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.repositories import mongo
from app.schemas.health import CheckResult

logger = logging.getLogger(__name__)


def check_mongodb(client: MongoClient) -> CheckResult:
    started = time.perf_counter()
    try:
        mongo.ping(client)
    except PyMongoError as error:
        logger.warning("Readiness: MongoDB indisponível: %s", error)
        return CheckResult(status="error", detail="MongoDB indisponível")
    return CheckResult(status="ok", latency_ms=round((time.perf_counter() - started) * 1000, 1))


def check_disk(settings: Settings) -> CheckResult:
    path = _nearest_existing(settings.attachments_path.resolve())
    free_mb = shutil.disk_usage(path).free // (1024 * 1024)
    if free_mb < settings.health_min_free_disk_mb:
        return CheckResult(status="degraded", detail=f"Espaço livre baixo: {free_mb} MB")
    return CheckResult(status="ok", detail=f"{free_mb} MB livres")


def overall_status(checks: dict[str, CheckResult]) -> str:
    statuses = {check.status for check in checks.values()}
    if "error" in statuses:
        return "error"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


def _nearest_existing(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path
