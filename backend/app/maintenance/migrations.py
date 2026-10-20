"""Migrations versionadas em ``database/migrations/NNNN_nome.py``.

Cada ficheiro define ``up(db)`` (e opcionalmente ``DESCRIPTION``). As migrations aplicadas ficam
registadas em ``schema_migrations``; um lock com expiração em ``maintenance_locks`` impede execuções
concorrentes. Não há transações (MongoDB 4.4 standalone), pelo que cada ``up`` tem de ser
idempotente: se falhar a meio, a próxima execução repete-a desde o início.
"""

import hashlib
import importlib.util
import re
import socket
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

MIGRATIONS_DIR = Path("migrations")
MIGRATIONS_COLLECTION = "schema_migrations"
LOCKS_COLLECTION = "maintenance_locks"
LOCK_ID = "migrations"
DEFAULT_LOCK_TTL = timedelta(minutes=15)

_FILE_PATTERN = re.compile(r"^(?P<number>\d{4})_(?P<name>[a-z0-9_]+)\.py$")


class MigrationError(RuntimeError):
    pass


class MigrationLockedError(MigrationError):
    pass


@dataclass(frozen=True)
class Migration:
    id: str
    number: int
    path: Path
    checksum: str
    description: str
    up: Callable[[Database], None]


@dataclass(frozen=True)
class MigrationStatus:
    id: str
    applied_at: datetime | None
    checksum_changed: bool = False
    missing_file: bool = False


def _load_module(migration_id: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"vcctf_migration_{migration_id}", path)
    if spec is None or spec.loader is None:
        raise MigrationError(f"Não foi possível carregar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_migrations(database_dir: Path) -> list[Migration]:
    directory = database_dir / MIGRATIONS_DIR
    migrations: list[Migration] = []
    numbers: dict[int, str] = {}
    for path in sorted(directory.glob("*.py")):
        match = _FILE_PATTERN.match(path.name)
        if match is None:
            if path.name != "__init__.py":
                raise MigrationError(f"Nome de migration inválido: {path.name} (NNNN_nome.py)")
            continue
        migration_id = path.stem
        number = int(match["number"])
        if number in numbers:
            raise MigrationError(f"Número de migration repetido: {numbers[number]} e {path.name}")
        numbers[number] = path.name
        module = _load_module(migration_id, path)
        up = getattr(module, "up", None)
        if not callable(up):
            raise MigrationError(f"{path.name} não define a função up(db)")
        migrations.append(
            Migration(
                id=migration_id,
                number=number,
                path=path,
                checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
                description=str(getattr(module, "DESCRIPTION", match["name"].replace("_", " "))),
                up=up,
            )
        )
    return migrations


def _applied(db: Database) -> dict[str, dict[str, Any]]:
    return {record["_id"]: record for record in db[MIGRATIONS_COLLECTION].find()}


def get_status(db: Database, migrations: list[Migration]) -> list[MigrationStatus]:
    applied = _applied(db)
    statuses = []
    for migration in migrations:
        record = applied.pop(migration.id, None)
        statuses.append(
            MigrationStatus(
                id=migration.id,
                applied_at=record["appliedAt"] if record else None,
                checksum_changed=bool(record) and record.get("checksum") != migration.checksum,
            )
        )
    for migration_id, record in sorted(applied.items()):
        statuses.append(
            MigrationStatus(id=migration_id, applied_at=record["appliedAt"], missing_file=True)
        )
    return statuses


def pending_migrations(db: Database, migrations: list[Migration]) -> list[Migration]:
    applied = _applied(db)
    return [migration for migration in migrations if migration.id not in applied]


@contextmanager
def migration_lock(db: Database, ttl: timedelta = DEFAULT_LOCK_TTL) -> Iterator[str]:
    """Lock exclusivo; expira sozinho se o processo terminar sem o libertar."""
    owner = f"{socket.gethostname()}:{uuid.uuid4().hex}"
    locks = db[LOCKS_COLLECTION]
    now = datetime.now(UTC)
    try:
        locks.update_one(
            {"_id": LOCK_ID, "lockedUntil": {"$lt": now}},
            {"$set": {"owner": owner, "lockedAt": now, "lockedUntil": now + ttl}},
            upsert=True,
        )
    except DuplicateKeyError as error:
        current = locks.find_one({"_id": LOCK_ID}) or {}
        raise MigrationLockedError(
            f"Migrations em execução por {current.get('owner', '?')} "
            f"(lock até {current.get('lockedUntil', '?')})"
        ) from error
    try:
        yield owner
    finally:
        locks.delete_one({"_id": LOCK_ID, "owner": owner})


def apply_migrations(db: Database, migrations: list[Migration]) -> list[Migration]:
    """Aplica por ordem as migrations pendentes e devolve as que foram aplicadas."""
    applied = []
    for migration in pending_migrations(db, migrations):
        started = time.perf_counter()
        try:
            migration.up(db)
        except Exception as error:
            raise MigrationError(f"A migration {migration.id} falhou: {error}") from error
        db[MIGRATIONS_COLLECTION].insert_one(
            {
                "_id": migration.id,
                "description": migration.description,
                "checksum": migration.checksum,
                "appliedAt": datetime.now(UTC),
                "durationMs": round((time.perf_counter() - started) * 1000, 1),
            }
        )
        applied.append(migration)
    return applied
