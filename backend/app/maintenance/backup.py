"""Backup, verificação e restauro da base de dados e dos anexos (DEV-025).

Cada backup é um único ficheiro ``vccteamforge-backup-<AAAAMMDDTHHMMSSZ>.tar.gz`` com:

- ``db/<collection>.bson``: os documentos em BSON bruto (tipos preservados sem conversões);
- ``attachments/<storageKey>``: os ficheiros dos anexos;
- ``manifest.json`` (último membro): versão do formato, data, versão do MongoDB, opções e índices
  de cada collection, número de documentos e tamanho/SHA-256 de cada membro.

Usa apenas o PyMongo (o ``mongodump`` não faz parte do servidor nem do venv). Sem replica set o
backup não é um instantâneo atómico: correr fora das horas de utilização (timer às 02:30).

O restauro verifica o arquivo inteiro antes de alterar o que quer que seja, guarda um backup de
segurança do estado atual e só depois substitui as collections e os anexos. Das collections
transitórias (sessões, tentativas de login, locks) guarda-se a estrutura, não os documentos:
depois de um restauro todos os utilizadores voltam a iniciar sessão.
"""

import contextlib
import hashlib
import io
import os
import re
import shutil
import tarfile
import tempfile
import time
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

import bson
from bson import json_util
from bson.codec_options import CodecOptions
from bson.errors import BSONError
from bson.raw_bson import RawBSONDocument
from pymongo.database import Database

from app.repositories import mongo
from app.storage.attachments import (
    DIR_MODE,
    FILE_MODE,
    AttachmentStorage,
    InvalidStorageKeyError,
)

FORMAT_VERSION = 1
ARCHIVE_PREFIX = "vccteamforge-backup-"
SAFETY_PREFIX = "vccteamforge-pre-restore-"
ARCHIVE_SUFFIX = ".tar.gz"
MANIFEST_NAME = "manifest.json"
DB_DIR = "db"
ATTACHMENTS_DIR = "attachments"
TRANSIENT_COLLECTIONS = frozenset({"sessions", "login_attempts", "maintenance_locks"})
ARCHIVE_MODE = 0o600
BACKUP_DIR_MODE = 0o750
INSERT_BATCH_SIZE = 500
# Folga exigida além do tamanho dos anexos (metadados, ficheiros temporários, manifesto).
FREE_SPACE_MARGIN_BYTES = 64 * 1024 * 1024
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
RESTORE_STAGING_PREFIX = ".restore-"

_SCHEDULED_ARCHIVE = re.compile(
    rf"^{re.escape(ARCHIVE_PREFIX)}\d{{8}}T\d{{6}}Z{re.escape(ARCHIVE_SUFFIX)}$"
)
_RAW_CODEC = CodecOptions(document_class=RawBSONDocument)
_JSON_OPTIONS = json_util.RELAXED_JSON_OPTIONS.with_options(tz_aware=True, tzinfo=UTC)
_INDEX_FIELDS_NOT_RESTORED = frozenset({"key", "v", "ns"})
_ARCHIVE_ERRORS = (tarfile.TarError, EOFError, OSError, ValueError, zlib.error)


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupResult:
    path: Path
    collections: int
    documents: int
    attachments: int
    attachment_bytes: int
    size: int
    removed: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class VerifiedBackup:
    path: Path
    manifest: dict[str, Any]

    @property
    def collections(self) -> list[dict[str, Any]]:
        return self.manifest["collections"]

    @property
    def documents(self) -> int:
        return sum(collection["documents"] for collection in self.collections)

    @property
    def attachments(self) -> int:
        return self.manifest["attachments"]["count"]

    @property
    def created_at(self) -> datetime:
        return self.manifest["createdAt"]


@dataclass(frozen=True)
class RestoreResult:
    collections: int
    documents: int
    attachments: int
    dropped: list[str]
    safety_backup: Path | None


class _HashingReader:
    """Calcula tamanho e SHA-256 do que é lido (para escrever e verificar numa só passagem)."""

    def __init__(self, raw: BinaryIO) -> None:
        self.raw = raw
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        self.digest.update(data)
        self.size += len(data)
        return data

    def drain(self) -> None:
        while self.read(1024 * 1024):
            pass

    @property
    def entry(self) -> dict[str, Any]:
        return {"size": self.size, "sha256": self.digest.hexdigest()}


# --- Criação -------------------------------------------------------------------------------------


def archive_name(now: datetime, prefix: str = ARCHIVE_PREFIX) -> str:
    return f"{prefix}{now.astimezone(UTC):{TIMESTAMP_FORMAT}}{ARCHIVE_SUFFIX}"


def list_backups(directory: Path) -> list[Path]:
    """Backups agendados/manuais da diretoria, do mais antigo para o mais recente."""
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if _SCHEDULED_ARCHIVE.fullmatch(path.name))


def _collection_infos(db: Database) -> list[dict[str, Any]]:
    infos = [
        info
        for info in db.list_collections()
        if info.get("type", "collection") == "collection" and not info["name"].startswith("system.")
    ]
    return sorted(infos, key=lambda info: info["name"])


def _add_member(tar: tarfile.TarFile, name: str, source: BinaryIO, size: int) -> dict[str, Any]:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o600
    info.mtime = int(time.time())
    reader = _HashingReader(source)
    tar.addfile(info, reader)
    return reader.entry


def _dump_collection(
    tar: tarfile.TarFile, db: Database, info: dict[str, Any], scratch_dir: Path
) -> dict[str, Any]:
    name = info["name"]
    collection = db.get_collection(name, codec_options=_RAW_CODEC)
    documents = 0
    with tempfile.TemporaryFile(dir=scratch_dir) as scratch:
        if name not in TRANSIENT_COLLECTIONS:
            for document in collection.find({}, batch_size=1000):
                scratch.write(document.raw)
                documents += 1
        size = scratch.tell()
        scratch.seek(0)
        member = _add_member(tar, f"{DB_DIR}/{name}.bson", scratch, size)
    indexes = [
        {key: value for key, value in index.items() if key != "ns"}
        for index in db[name].list_indexes()
    ]
    return {
        "name": name,
        "documents": documents,
        "options": info.get("options", {}),
        "indexes": indexes,
        **member,
    }


def _dump_attachments(tar: tarfile.TarFile, root: Path) -> tuple[dict[str, Any], int, int]:
    """Ficheiros com nomes fora do formato dos anexos (ex.: restos de um restauro) são ignorados."""
    storage = AttachmentStorage(root)
    files: dict[str, Any] = {}
    total = 0
    for key in sorted(storage.iter_keys()):
        try:
            path = storage.path_for(key)
        except InvalidStorageKeyError:
            continue
        with path.open("rb") as source:
            size = os.fstat(source.fileno()).st_size
            files[key] = _add_member(tar, f"{ATTACHMENTS_DIR}/{key}", source, size)
        total += size
    return files, len(files), total


def _attachments_bytes(root: Path) -> int:
    storage = AttachmentStorage(root)
    total = 0
    for key in storage.iter_keys():
        with contextlib.suppress(InvalidStorageKeyError, OSError):
            total += storage.path_for(key).stat().st_size
    return total


def _check_free_space(needs: dict[Path, int]) -> None:
    """Falha antes de alterar dados se algum sistema de ficheiros não tiver espaço suficiente."""
    by_device: dict[int, tuple[Path, int]] = {}
    for path, size in needs.items():
        device = path.stat().st_dev
        first, total = by_device.get(device, (path, 0))
        by_device[device] = (first, total + size)
    for path, size in by_device.values():
        free = shutil.disk_usage(path).free
        if free < size + FREE_SPACE_MARGIN_BYTES:
            raise BackupError(
                f"Espaço insuficiente em {path}: {free // 2**20} MiB livres, "
                f"são precisos cerca de {(size + FREE_SPACE_MARGIN_BYTES) // 2**20} MiB"
            )


def _write_manifest(tar: tarfile.TarFile, manifest: dict[str, Any]) -> None:
    data = json_util.dumps(manifest, json_options=_JSON_OPTIONS, indent=2, ensure_ascii=False)
    payload = data.encode("utf-8")
    _add_member(tar, MANIFEST_NAME, io.BytesIO(payload), len(payload))


def _open_private(path: Path) -> BinaryIO:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, ARCHIVE_MODE)
    return os.fdopen(fd, "wb")


def create_backup(
    db: Database,
    attachments_path: Path,
    output_dir: Path,
    *,
    now: datetime | None = None,
    prefix: str = ARCHIVE_PREFIX,
) -> BackupResult:
    """Escreve o backup para ``<nome>.partial`` e só no fim o renomeia (nunca fica a meio)."""
    now = now or datetime.now(UTC)
    output_dir.mkdir(mode=BACKUP_DIR_MODE, parents=True, exist_ok=True)
    target = output_dir / archive_name(now, prefix)
    if target.exists():
        raise BackupError(f"Já existe um backup com o nome {target.name}")
    partial = target.with_name(target.name + ".partial")
    server = mongo.get_server_info(db.client)
    try:
        with (
            _open_private(partial) as raw,
            tarfile.open(fileobj=raw, mode="w:gz", compresslevel=6) as tar,
        ):
            collections = [
                _dump_collection(tar, db, info, output_dir) for info in _collection_infos(db)
            ]
            files, count, total = _dump_attachments(tar, attachments_path)
            _write_manifest(
                tar,
                {
                    "format": FORMAT_VERSION,
                    "createdAt": now,
                    "database": db.name,
                    "mongodbVersion": server.version,
                    "collections": collections,
                    "attachments": {"count": count, "bytes": total, "files": files},
                },
            )
        with partial.open("rb") as written:
            os.fsync(written.fileno())
        os.replace(partial, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            partial.unlink()
        raise
    return BackupResult(
        path=target,
        collections=len(collections),
        documents=sum(collection["documents"] for collection in collections),
        attachments=count,
        attachment_bytes=total,
        size=target.stat().st_size,
    )


def prune_backups(directory: Path, keep: int) -> list[Path]:
    """Remove os backups mais antigos, mantendo os ``keep`` mais recentes."""
    backups = list_backups(directory)
    removed = backups[: max(len(backups) - keep, 0)]
    for path in removed:
        path.unlink()
    return removed


# --- Leitura e verificação ---------------------------------------------------------------------


def _attachment_key(member_name: str) -> str | None:
    parts = PurePosixPath(member_name).parts
    if len(parts) < 2 or parts[0] != ATTACHMENTS_DIR:
        return None
    return "/".join(parts[1:])


def _iter_members(path: Path) -> Iterator[tuple[tarfile.TarInfo, BinaryIO]]:
    """Percorre o arquivo em streaming, recusando tudo o que não seja um ficheiro esperado."""
    try:
        with tarfile.open(path, mode="r|gz") as tar:
            for member in tar:
                name = member.name
                if not member.isfile():
                    raise BackupError(f"Membro inesperado no arquivo: {name}")
                is_known = name == MANIFEST_NAME or (
                    name.startswith(f"{DB_DIR}/")
                    and name.endswith(".bson")
                    and name.count("/") == 1
                )
                key = _attachment_key(name)
                if key is not None:
                    try:
                        AttachmentStorage(Path("/")).path_for(key)
                    except InvalidStorageKeyError as error:
                        raise BackupError(f"Nome de anexo inválido no arquivo: {name}") from error
                elif not is_known:
                    raise BackupError(f"Membro inesperado no arquivo: {name}")
                source = tar.extractfile(member)
                if source is None:
                    raise BackupError(f"Membro ilegível no arquivo: {name}")
                yield member, source
    except _ARCHIVE_ERRORS as error:
        raise BackupError(f"Arquivo corrompido ou ilegível ({path.name}): {error}") from error


def _load_manifest(payload: bytes) -> dict[str, Any]:
    try:
        manifest = json_util.loads(payload.decode("utf-8"), json_options=_JSON_OPTIONS)
    except (UnicodeDecodeError, ValueError) as error:
        raise BackupError(f"Manifesto inválido: {error}") from error
    if manifest.get("format") != FORMAT_VERSION:
        raise BackupError(f"Formato de backup não suportado: {manifest.get('format')!r}")
    return manifest


def _count_bson(reader: _HashingReader) -> int:
    try:
        count = sum(1 for _ in bson.decode_file_iter(reader, codec_options=_RAW_CODEC))
    except BSONError as error:
        raise BackupError(f"BSON inválido: {error}") from error
    reader.drain()
    return count


def verify_backup(path: Path) -> VerifiedBackup:
    """Lê o arquivo inteiro: checksums, tamanhos, BSON legível e contagens iguais ao manifesto."""
    seen: dict[str, dict[str, Any]] = {}
    manifest: dict[str, Any] | None = None
    try:
        for member, source in _iter_members(path):
            if member.name == MANIFEST_NAME:
                if manifest is not None:
                    raise BackupError("Manifesto duplicado")
                manifest = _load_manifest(source.read())
                continue
            if member.name in seen:
                raise BackupError(f"Membro duplicado: {member.name}")
            reader = _HashingReader(source)
            documents = _count_bson(reader) if member.name.startswith(f"{DB_DIR}/") else None
            if documents is None:
                reader.drain()
            seen[member.name] = {**reader.entry, "documents": documents}
    except _ARCHIVE_ERRORS as error:
        raise BackupError(f"Arquivo corrompido ou ilegível ({path.name}): {error}") from error
    if manifest is None:
        raise BackupError("Arquivo sem manifesto (backup incompleto?)")

    expected: dict[str, dict[str, Any]] = {}
    for collection in manifest["collections"]:
        expected[f"{DB_DIR}/{collection['name']}.bson"] = collection
    for key, entry in manifest["attachments"]["files"].items():
        expected[f"{ATTACHMENTS_DIR}/{key}"] = {**entry, "documents": None}

    missing = sorted(set(expected) - set(seen))
    extra = sorted(set(seen) - set(expected))
    if missing or extra:
        raise BackupError(f"Conteúdo diferente do manifesto (em falta: {missing}, a mais: {extra})")
    for name, entry in expected.items():
        actual = seen[name]
        if (actual["size"], actual["sha256"]) != (entry["size"], entry["sha256"]):
            raise BackupError(f"Checksum inválido: {name}")
        if entry["documents"] is not None and actual["documents"] != entry["documents"]:
            raise BackupError(
                f"{name}: {actual['documents']} documento(s), manifesto indica {entry['documents']}"
            )
    return VerifiedBackup(path=path, manifest=manifest)


# --- Restauro ----------------------------------------------------------------------------------


def _restore_collection(db: Database, spec: dict[str, Any], source: BinaryIO) -> int:
    name = spec["name"]
    db.drop_collection(name)
    db.create_collection(name, **spec["options"])
    collection = db.get_collection(name, codec_options=_RAW_CODEC)
    batch: list[RawBSONDocument] = []
    inserted = 0
    for document in bson.decode_file_iter(source, codec_options=_RAW_CODEC):
        batch.append(document)
        if len(batch) >= INSERT_BATCH_SIZE:
            collection.insert_many(batch, bypass_document_validation=True)
            inserted += len(batch)
            batch = []
    if batch:
        collection.insert_many(batch, bypass_document_validation=True)
        inserted += len(batch)
    for index in spec["indexes"]:
        if index["name"] == "_id_":
            continue
        options = {k: v for k, v in index.items() if k not in _INDEX_FIELDS_NOT_RESTORED}
        db[name].create_index(list(index["key"].items()), **options)
    return inserted


def _stage_attachment(staging: Path, key: str, source: BinaryIO) -> None:
    target = AttachmentStorage(staging).path_for(key)
    current = staging
    for part in PurePosixPath(key).parent.parts:
        current = current / part
        with contextlib.suppress(FileExistsError):
            current.mkdir(mode=DIR_MODE)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(fd, "wb") as handle:
        shutil.copyfileobj(source, handle, 1024 * 1024)


def _swap_attachments(root: Path, staging: Path) -> None:
    """Substitui o conteúdo de ``root`` pelo de ``staging`` (que está dentro de ``root``).

    Fica tudo no mesmo sistema de ficheiros, mesmo que ``root`` seja um ponto de montagem.
    """
    for entry in root.iterdir():
        if entry == staging:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for entry in staging.iterdir():
        os.replace(entry, root / entry.name)
    staging.rmdir()


def restore_backup(
    db: Database,
    attachments_path: Path,
    archive: Path,
    *,
    safety_backup_dir: Path | None,
    progress: Callable[[str], None] = lambda _message: None,
) -> RestoreResult:
    """Substitui a BD e os anexos pelo conteúdo do arquivo (que é verificado primeiro).

    A API deve estar parada. Collections que não existam no backup são removidas.
    """
    progress(f"A verificar {archive.name}...")
    verified = verify_backup(archive)
    specs = {f"{DB_DIR}/{spec['name']}.bson": spec for spec in verified.collections}

    attachments_path.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    needs = {attachments_path: verified.manifest["attachments"]["bytes"]}
    if safety_backup_dir is not None:
        safety_backup_dir.mkdir(mode=BACKUP_DIR_MODE, parents=True, exist_ok=True)
        needs[safety_backup_dir] = _attachments_bytes(attachments_path)
    _check_free_space(needs)

    safety_path = None
    if safety_backup_dir is not None:
        progress("A criar backup de segurança do estado atual...")
        safety_path = create_backup(
            db, attachments_path, safety_backup_dir, prefix=SAFETY_PREFIX
        ).path
        progress(f"Backup de segurança: {safety_path}")

    staging = Path(tempfile.mkdtemp(prefix=RESTORE_STAGING_PREFIX, dir=attachments_path))
    os.chmod(staging, DIR_MODE)
    documents = 0
    attachments = 0
    try:
        progress("A restaurar collections e a preparar os anexos...")
        for member, source in _iter_members(archive):
            if member.name in specs:
                documents += _restore_collection(db, specs[member.name], source)
            elif (key := _attachment_key(member.name)) is not None:
                _stage_attachment(staging, key, source)
                attachments += 1
        restored = {spec["name"] for spec in verified.collections}
        dropped = [info["name"] for info in _collection_infos(db) if info["name"] not in restored]
        for name in dropped:
            db.drop_collection(name)
        progress("A substituir os anexos...")
        _swap_attachments(attachments_path, staging)
    except BaseException as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if not isinstance(exc, Exception) or safety_path is None:
            raise
        raise BackupError(
            f"Restauro interrompido ({exc}); a BD pode ter ficado incompleta e os anexos não "
            f"foram alterados. Repor o estado anterior com: restore {safety_path} --yes "
            "--no-safety-backup"
        ) from exc
    return RestoreResult(
        collections=len(specs),
        documents=documents,
        attachments=attachments,
        dropped=dropped,
        safety_backup=safety_path,
    )
