import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pymongo.database import Database

from app import cli
from app.core.config import DEFAULT_DATABASE_DIR, Settings
from app.maintenance import indexes, migrations, seeds

README_INDEXES = {
    ("projects", (("key", 1),), True),
    ("users", (("normalizedEmail", 1),), True),
    ("issues", (("projectId", 1), ("number", 1)), True),
    ("issues", (("projectId", 1), ("status", 1)), False),
    ("issues", (("sprintId", 1), ("status", 1)), False),
    ("issues", (("assigneeId", 1), ("status", 1)), False),
    ("issue_history", (("issueId", 1), ("createdAt", -1)), False),
    ("sprints", (("projectId", 1), ("status", 1)), False),
    ("test_runs", (("projectId", 1), ("executedAt", -1)), False),
}


def _spec(collection: str, name: str, keys: list, **options) -> indexes.IndexSpec:
    return indexes.IndexSpec(collection=collection, name=name, keys=keys, options=options)


def _write_migration(directory: Path, filename: str, body: str) -> None:
    (directory / "migrations").mkdir(parents=True, exist_ok=True)
    (directory / "migrations" / filename).write_text(body, encoding="utf-8")


def test_repository_indexes_include_readme_indexes():
    specs = indexes.load_index_specs(DEFAULT_DATABASE_DIR)
    declared = {(spec.collection, tuple(spec.keys), spec.options.unique) for spec in specs}
    assert README_INDEXES.issubset(declared)


def test_repository_migrations_and_seeds_are_valid():
    assert [m.id for m in migrations.discover_migrations(DEFAULT_DATABASE_DIR)][0] == (
        "0001_initial_collections"
    )
    assert "global" in [doc["_id"] for doc in seeds.load_seeds(DEFAULT_DATABASE_DIR)["settings"]]


def test_duplicate_index_names_are_rejected(tmp_path: Path):
    (tmp_path / "indexes").mkdir()
    entry = {"collection": "a", "name": "dup", "keys": [["x", 1]]}
    (tmp_path / "indexes" / "indexes.json").write_text(json.dumps({"indexes": [entry, entry]}))
    with pytest.raises(ValueError, match="duplicado"):
        indexes.load_index_specs(tmp_path)


def test_ensure_indexes_is_idempotent(db: Database):
    specs = [
        _spec("sessions", "sessions_tokenHash_unique", [("tokenHash", 1)], unique=True),
        _spec("sessions", "sessions_expiresAt_ttl", [("expiresAt", 1)], expireAfterSeconds=0),
    ]
    first = indexes.ensure_indexes(db, specs)
    second = indexes.ensure_indexes(db, specs)

    assert {r.action for r in first} == {indexes.IndexAction.CREATED}
    assert {r.action for r in second} == {indexes.IndexAction.UNCHANGED}
    info = db.sessions.index_information()
    assert info["sessions_tokenHash_unique"]["unique"] is True
    assert info["sessions_expiresAt_ttl"]["expireAfterSeconds"] == 0


def test_dry_run_does_not_create_indexes(db: Database):
    result = indexes.ensure_indexes(db, [_spec("projects", "p_key", [("key", 1)])], dry_run=True)
    assert result[0].action is indexes.IndexAction.PENDING
    assert "projects" not in db.list_collection_names()


def test_conflicting_index_aborts_before_creating_anything(db: Database):
    db.projects.create_index([("key", 1)], name="projects_key_unique")
    specs = [
        _spec("projects", "projects_memberIds", [("memberIds", 1)]),
        _spec("projects", "projects_key_unique", [("key", 1)], unique=True),
    ]
    with pytest.raises(indexes.IndexConflictError):
        indexes.ensure_indexes(db, specs)
    assert "projects_memberIds" not in db.projects.index_information()


def test_equivalent_index_with_other_name_is_accepted(db: Database):
    db.projects.create_index([("key", 1)], name="key_1", unique=True)
    result = indexes.ensure_indexes(
        db, [_spec("projects", "projects_key_unique", [("key", 1)], unique=True)]
    )
    assert result[0].action is indexes.IndexAction.EXISTS_WITH_OTHER_NAME
    assert result[0].existing_name == "key_1"


def test_migrations_apply_in_order_once(db: Database, tmp_path: Path):
    _write_migration(
        tmp_path,
        "0002_second.py",
        "def up(db):\n    db.log.update_one({'_id': 2}, {'$set': {'n': 2}}, upsert=True)\n",
    )
    _write_migration(
        tmp_path,
        "0001_first.py",
        "DESCRIPTION = 'Primeira'\n"
        "def up(db):\n    assert db.log.count_documents({}) == 0\n"
        "    db.log.insert_one({'_id': 1})\n",
    )
    available = migrations.discover_migrations(tmp_path)

    applied = migrations.apply_migrations(db, available)
    again = migrations.apply_migrations(db, available)

    assert [m.id for m in applied] == ["0001_first", "0002_second"]
    assert again == []
    record = db.schema_migrations.find_one({"_id": "0001_first"})
    assert record["description"] == "Primeira"
    assert record["checksum"] == available[0].checksum


def test_failed_migration_is_not_recorded(db: Database, tmp_path: Path):
    _write_migration(tmp_path, "0001_ok.py", "def up(db):\n    pass\n")
    _write_migration(tmp_path, "0002_boom.py", "def up(db):\n    raise RuntimeError('boom')\n")

    with pytest.raises(migrations.MigrationError, match="0002_boom.*boom"):
        migrations.apply_migrations(db, migrations.discover_migrations(tmp_path))

    assert [r["_id"] for r in db.schema_migrations.find()] == ["0001_ok"]


def test_status_reports_pending_changed_and_missing(db: Database, tmp_path: Path):
    _write_migration(tmp_path, "0001_a.py", "def up(db):\n    pass\n")
    _write_migration(tmp_path, "0002_b.py", "def up(db):\n    pass\n")
    migrations.apply_migrations(db, migrations.discover_migrations(tmp_path)[:1])
    db.schema_migrations.insert_one({"_id": "0000_removed", "appliedAt": datetime.now(UTC)})
    _write_migration(tmp_path, "0001_a.py", "def up(db):\n    return None\n")

    statuses = {
        s.id: s for s in migrations.get_status(db, migrations.discover_migrations(tmp_path))
    }

    assert statuses["0001_a"].checksum_changed
    assert statuses["0002_b"].applied_at is None
    assert statuses["0000_removed"].missing_file


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"1_bad.py": "def up(db): pass\n"}, "inválido"),
        ({"0001_a.py": "def up(db): pass\n", "0001_b.py": "def up(db): pass\n"}, "repetido"),
        ({"0001_a.py": "x = 1\n"}, "up"),
    ],
)
def test_invalid_migration_files_are_rejected(tmp_path: Path, files: dict, message: str):
    for filename, body in files.items():
        _write_migration(tmp_path, filename, body)
    with pytest.raises(migrations.MigrationError, match=message):
        migrations.discover_migrations(tmp_path)


def test_migration_lock_is_exclusive_and_released(db: Database):
    with (
        migrations.migration_lock(db),
        pytest.raises(migrations.MigrationLockedError),
        migrations.migration_lock(db),
    ):
        pass
    with migrations.migration_lock(db):
        pass
    assert db.maintenance_locks.count_documents({}) == 0


def test_expired_migration_lock_is_taken_over(db: Database):
    expired = datetime.now(UTC) - timedelta(minutes=1)
    db.maintenance_locks.insert_one(
        {"_id": migrations.LOCK_ID, "owner": "crashed", "lockedUntil": expired}
    )
    with migrations.migration_lock(db) as owner:
        assert db.maintenance_locks.find_one()["owner"] == owner


def test_seeds_insert_only_missing_documents(db: Database):
    data = {"settings": [{"_id": "global", "scrum": {"sprintDurationDays": 14}}]}

    first = seeds.apply_seeds(db, data)
    db.settings.update_one({"_id": "global"}, {"$set": {"scrum.sprintDurationDays": 10}})
    second = seeds.apply_seeds(db, data)

    assert (first[0].inserted, second[0].existing) == (1, 1)
    document = db.settings.find_one({"_id": "global"})
    assert document["scrum"]["sprintDurationDays"] == 10
    assert document["createdAt"].tzinfo is not None


def test_seed_documents_require_id(tmp_path: Path):
    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "settings.json").write_text('{"documents": [{"x": 1}]}')
    with pytest.raises(ValueError, match="_id"):
        seeds.load_seeds(tmp_path)


def _run_cli(*args: str, settings: Settings, client) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = cli.main(list(args), settings=settings, client=client, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_cli_migrate_seed_and_status(db: Database, mongo_settings: Settings, mongo_client):
    total = len(indexes.load_index_specs(DEFAULT_DATABASE_DIR))

    code, out, _ = _run_cli("migrate", settings=mongo_settings, client=mongo_client)
    assert code == 0
    assert f"1 migration(s) e {total} índice(s) novos" in out

    code, out, _ = _run_cli("migrate", settings=mongo_settings, client=mongo_client)
    assert "0 migration(s) e 0 índice(s) novos" in out

    code, out, _ = _run_cli("seed", settings=mongo_settings, client=mongo_client)
    assert "Seed settings: 1 inserido(s)" in out
    assert db.settings.find_one({"_id": "global"})["scrum"]["sprintDurationDays"] == 14

    code, out, _ = _run_cli("status", settings=mongo_settings, client=mongo_client)
    assert "0001_initial_collections: aplicada" in out
    assert f"Índices: {total}/{total} presentes" in out


def test_cli_reports_conflicts(db: Database, mongo_settings: Settings, mongo_client):
    db.projects.create_index([("name", 1)], name="projects_key_unique")

    code, _, err = _run_cli("migrate", settings=mongo_settings, client=mongo_client)

    assert code == 1
    assert "projects.projects_key_unique" in err
    assert db.maintenance_locks.count_documents({}) == 0
