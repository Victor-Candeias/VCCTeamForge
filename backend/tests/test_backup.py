import io
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from bson import Decimal128, ObjectId
from pymongo.database import Database

from app import cli
from app.core.config import Settings
from app.maintenance import backup
from app.storage.attachments import AttachmentStorage

NOW = datetime(2026, 10, 21, 2, 30, tzinfo=UTC)


@pytest.fixture
def settings(mongo_settings: Settings, tmp_path: Path) -> Settings:
    return mongo_settings.model_copy(
        update={
            "attachments_path": tmp_path / "attachments",
            "backup_path": tmp_path / "backups",
            "backup_retention": 3,
        }
    )


def _run_cli(*args: str, settings: Settings, client) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = cli.main(list(args), settings=settings, client=client, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _populate(db: Database, settings: Settings) -> dict:
    db.create_collection(
        "projects", validator={"$jsonSchema": {"bsonType": "object", "required": ["key"]}}
    )
    db.projects.create_index([("key", 1)], name="projects_key_unique", unique=True)
    db.issues.create_index(
        [("projectId", 1), ("number", -1)],
        name="issues_partial",
        partialFilterExpression={"deletedAt": None},
    )
    project = {
        "_id": ObjectId(),
        "key": "ALFA",
        "name": "Ação — çãõ 🚀",
        "createdAt": datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=UTC),
        "budget": Decimal128("12.50"),
        "tags": ["a", {"nested": [1, 2.5, None, True]}],
    }
    db.projects.insert_one(project)
    db.issues.insert_many([{"projectId": project["_id"], "number": n} for n in range(1, 1201)])
    db.sessions.insert_one({"tokenHash": "secret", "expiresAt": NOW})
    stored = AttachmentStorage(settings.attachments_path).save(
        str(project["_id"]), io.BytesIO(b"\x00binary\xffdata"), max_bytes=1024, now=NOW
    )
    return {"project": project, "storage_key": stored.storage_key}


def _rewrite_archive(source: Path, target: Path, transform) -> None:
    """Copia o arquivo membro a membro, deixando ``transform`` alterar nome/conteúdo."""
    with tarfile.open(source, "r:gz") as old, tarfile.open(target, "w:gz") as new:
        for member in old.getmembers():
            data = old.extractfile(member).read()
            result = transform(member.name, data)
            if result is None:
                continue
            name, data = result
            info = tarfile.TarInfo(name)
            info.size = len(data)
            new.addfile(info, io.BytesIO(data))


def test_backup_and_restore_round_trip(db: Database, settings: Settings, mongo_client):
    data = _populate(db, settings)
    original_project = db.projects.find_one()

    code, out, err = _run_cli("backup", settings=settings, client=mongo_client)
    assert code == 0, err
    [archive] = backup.list_backups(settings.backup_path)
    assert "Backup criado" in out
    assert archive.stat().st_mode & 0o777 == 0o600

    code, out, _ = _run_cli("backup-verify", str(archive), settings=settings, client=mongo_client)
    assert code == 0
    assert "issues: 1200 documento(s)" in out
    assert "sessions: 0 documento(s)" in out

    # Alterações depois do backup, que o restauro tem de desfazer.
    db.projects.update_one({}, {"$set": {"name": "alterado"}})
    db.issues.delete_many({"number": {"$gt": 10}})
    db.create_collection("extra")
    storage = AttachmentStorage(settings.attachments_path)
    storage.delete(data["storage_key"])
    storage.save(str(ObjectId()), io.BytesIO(b"novo"), max_bytes=1024, now=NOW)

    code, _, err = _run_cli("restore", str(archive), settings=settings, client=mongo_client)
    assert code == 1
    assert "--yes" in err
    assert db.issues.count_documents({}) == 10

    code, out, err = _run_cli(
        "restore", str(archive), "--yes", settings=settings, client=mongo_client
    )
    assert code == 0, err
    assert "removida (não existe no backup): extra" in out

    assert db.projects.find_one() == original_project
    assert db.issues.count_documents({}) == 1200
    assert db.sessions.count_documents({}) == 0
    assert "extra" not in db.list_collection_names()
    options = db.projects.options()
    assert options["validator"]["$jsonSchema"]["required"] == ["key"]
    project_indexes = db.projects.index_information()
    assert project_indexes["projects_key_unique"]["unique"] is True
    partial = db.issues.index_information()["issues_partial"]
    assert partial["key"] == [("projectId", 1), ("number", -1)]
    assert partial["partialFilterExpression"] == {"deletedAt": None}
    assert sorted(storage.iter_keys()) == [data["storage_key"]]
    assert storage.path_for(data["storage_key"]).read_bytes() == b"\x00binary\xffdata"
    assert [p.name for p in settings.attachments_path.iterdir()] == [
        data["storage_key"].split("/")[0]
    ]

    # O estado anterior ao restauro ficou guardado e é um backup válido.
    [safety] = settings.backup_path.glob(f"{backup.SAFETY_PREFIX}*")
    assert backup.verify_backup(safety).documents == 11
    assert backup.list_backups(settings.backup_path) == [archive]


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (
            lambda name, data: (name, data.replace(b"ALFA", b"BETA")),
            "Checksum",
        ),
        (lambda name, data: None if name == "manifest.json" else (name, data), "sem manifesto"),
        (
            lambda name, data: (
                ("attachments/../../etc/passwd", data)
                if name.startswith("attachments/")
                else (name, data)
            ),
            "inválido",
        ),
        (
            lambda name, data: (name, data) if name != "db/projects.bson" else None,
            "em falta",
        ),
    ],
    ids=["checksum", "manifest", "traversal", "missing"],
)
def test_invalid_archives_are_rejected_before_touching_data(
    db: Database, settings: Settings, mongo_client, tmp_path: Path, transform, message
):
    _populate(db, settings)
    result = backup.create_backup(db, settings.attachments_path, settings.backup_path, now=NOW)
    tampered = tmp_path / "tampered.tar.gz"
    _rewrite_archive(result.path, tampered, transform)
    db.issues.delete_many({})

    with pytest.raises(backup.BackupError, match=message):
        backup.verify_backup(tampered)
    code, _, err = _run_cli(
        "restore", str(tampered), "--yes", settings=settings, client=mongo_client
    )

    assert code == 1
    assert message in err
    assert db.issues.count_documents({}) == 0
    assert not list(settings.backup_path.glob(f"{backup.SAFETY_PREFIX}*"))


def test_truncated_archive_is_rejected(db: Database, settings: Settings, tmp_path: Path):
    _populate(db, settings)
    result = backup.create_backup(db, settings.attachments_path, settings.backup_path, now=NOW)
    truncated = tmp_path / "truncated.tar.gz"
    truncated.write_bytes(result.path.read_bytes()[:-200])

    with pytest.raises(backup.BackupError):
        backup.verify_backup(truncated)


def test_restore_failures_preserve_data_or_point_to_safety_backup(
    db: Database, settings: Settings, monkeypatch
):
    data = _populate(db, settings)
    archive = backup.create_backup(
        db, settings.attachments_path, settings.backup_path, now=NOW
    ).path
    db.issues.delete_many({})
    usage = backup.shutil.disk_usage(settings.backup_path)

    monkeypatch.setattr(backup.shutil, "disk_usage", lambda _path: usage._replace(free=1024))
    with pytest.raises(backup.BackupError, match="Espaço insuficiente"):
        backup.restore_backup(
            db, settings.attachments_path, archive, safety_backup_dir=settings.backup_path
        )
    assert db.issues.count_documents({}) == 0
    assert not list(settings.backup_path.glob(f"{backup.SAFETY_PREFIX}*"))

    monkeypatch.setattr(backup.shutil, "disk_usage", lambda _path: usage._replace(free=usage.total))

    def disk_full(*_args):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(backup, "_stage_attachment", disk_full)
    with pytest.raises(backup.BackupError, match="Repor o estado anterior") as raised:
        backup.restore_backup(
            db, settings.attachments_path, archive, safety_backup_dir=settings.backup_path
        )
    [safety] = settings.backup_path.glob(f"{backup.SAFETY_PREFIX}*")
    assert str(safety) in str(raised.value)
    assert AttachmentStorage(settings.attachments_path).path_for(data["storage_key"]).exists()
    assert not list(settings.attachments_path.glob(f"{backup.RESTORE_STAGING_PREFIX}*"))


def test_retention_keeps_most_recent_backups(db: Database, settings: Settings, mongo_client):
    _populate(db, settings)
    old = [
        backup.create_backup(
            db, settings.attachments_path, settings.backup_path, now=NOW - timedelta(days=days)
        ).path
        for days in (4, 3, 2)
    ]
    unrelated = settings.backup_path / "notas.txt"
    unrelated.write_text("x")

    code, out, err = _run_cli("backup", "--keep", "2", settings=settings, client=mongo_client)

    assert code == 0, err
    backups = backup.list_backups(settings.backup_path)
    assert len(backups) == 2
    assert backups[0] == old[2]
    assert out.count("removido (retenção de 2)") == 2
    assert unrelated.exists()
    assert not list(settings.backup_path.glob("*.partial"))

    code, out, _ = _run_cli("status", settings=settings, client=mongo_client)
    assert code == 0
    assert f"Último backup: {backups[-1].name}" in out
