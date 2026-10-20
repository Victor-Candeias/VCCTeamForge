"""CLI de manutenção da base de dados.

Uso (a partir de ``backend/``)::

    python -m app.cli status            # migrations aplicadas/pendentes e índices em falta
    python -m app.cli migrate [--dry-run]
    python -m app.cli seed
    python -m app.cli create-user --email admin@exemplo.pt --name "Admin" [--role admin]
    python -m app.cli attachments-check # ficheiros órfãos e anexos sem ficheiro
    python -m app.cli report-snapshots  # snapshot diário dos KPIs de cada projeto

A password do ``create-user`` é pedida no terminal ou lida de ``VCCTF_NEW_USER_PASSWORD``
(nunca como argumento, para não ficar no histórico da shell).

Lê a mesma configuração que a API (variáveis de ambiente / ``VCCTF_ENV_FILE``).
"""

import argparse
import getpass
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings, get_settings
from app.domain.permissions import Role
from app.maintenance import indexes, migrations, seeds
from app.repositories import mongo
from app.repositories.attachments import AttachmentRepository
from app.repositories.users import EmailAlreadyExistsError
from app.services.analytics import ReportSnapshotService
from app.services.users import UserService
from app.storage.attachments import AttachmentStorage

PASSWORD_ENV = "VCCTF_NEW_USER_PASSWORD"  # noqa: S105 (nome da variável, não o segredo)


class _Output:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def __call__(self, message: str = "") -> None:
        print(message, file=self.stream)


def _status(db: Database, settings: Settings, out: _Output) -> int:
    statuses = migrations.get_status(db, migrations.discover_migrations(settings.database_dir))
    out("Migrations:")
    for status in statuses:
        if status.missing_file:
            state = f"aplicada {status.applied_at:%Y-%m-%d %H:%M} (ficheiro em falta)"
        elif status.applied_at is None:
            state = "pendente"
        else:
            state = f"aplicada {status.applied_at:%Y-%m-%d %H:%M}"
            if status.checksum_changed:
                state += " (ficheiro alterado depois de aplicada)"
        out(f"  {status.id}: {state}")
    plan = indexes.ensure_indexes(db, indexes.load_index_specs(settings.database_dir), dry_run=True)
    missing = [result.spec for result in plan if result.action is indexes.IndexAction.PENDING]
    out(f"Índices: {len(plan) - len(missing)}/{len(plan)} presentes")
    for spec in missing:
        out(f"  em falta: {spec.collection}.{spec.name}")
    return 0


def _migrate(db: Database, settings: Settings, out: _Output, *, dry_run: bool) -> int:
    available = migrations.discover_migrations(settings.database_dir)
    specs = indexes.load_index_specs(settings.database_dir)
    if dry_run:
        for migration in migrations.pending_migrations(db, available):
            out(f"[dry-run] migration {migration.id}: {migration.description}")
        for result in indexes.ensure_indexes(db, specs, dry_run=True):
            if result.action is indexes.IndexAction.PENDING:
                out(f"[dry-run] índice {result.spec.collection}.{result.spec.name}")
        return 0

    with migrations.migration_lock(db):
        applied = migrations.apply_migrations(db, available)
        index_results = indexes.ensure_indexes(db, specs)
    for migration in applied:
        out(f"Migration aplicada: {migration.id}")
    for result in index_results:
        if result.action is indexes.IndexAction.CREATED:
            out(f"Índice criado: {result.spec.collection}.{result.spec.name}")
        elif result.action is indexes.IndexAction.EXISTS_WITH_OTHER_NAME:
            out(
                f"Aviso: {result.spec.collection}.{result.spec.name} já existe como "
                f"{result.existing_name}"
            )
    created = sum(result.action is indexes.IndexAction.CREATED for result in index_results)
    out(f"Concluído: {len(applied)} migration(s) e {created} índice(s) novos.")
    return 0


def _seed(db: Database, settings: Settings, out: _Output) -> int:
    for result in seeds.apply_seeds(db, seeds.load_seeds(settings.database_dir)):
        out(
            f"Seed {result.collection}: {result.inserted} inserido(s), "
            f"{result.existing} existente(s)"
        )
    return 0


def _report_snapshots(db: Database, out: _Output) -> int:
    """Snapshot de hoje (substituído se já existir) para cada projeto não arquivado."""
    saved, failed = ReportSnapshotService(db).capture_all()
    out(f"Snapshots de relatório: {saved} gravado(s), {failed} com erro.")
    return 1 if failed else 0


def _attachments_check(db: Database, settings: Settings, out: _Output) -> int:
    """Compara o disco com os metadados ativos; devolve 1 se houver inconsistências."""
    on_disk = set(AttachmentStorage(settings.attachments_path).iter_keys())
    expected = AttachmentRepository(db).active_storage_keys()
    orphans = sorted(on_disk - expected)
    missing = sorted(expected - on_disk)
    out(
        f"Anexos: {len(expected)} ativos, {len(on_disk)} ficheiro(s) em {settings.attachments_path}"
    )
    for key in orphans:
        out(f"  órfão (sem metadados ativos): {key}")
    for key in missing:
        out(f"  em falta no disco: {key}")
    if orphans or missing:
        out(f"Inconsistências: {len(orphans)} órfão(s), {len(missing)} em falta.")
        return 1
    out("Sem inconsistências.")
    return 0


def _read_password() -> str:
    password = os.environ.get(PASSWORD_ENV)
    if password:
        return password
    if not sys.stdin.isatty():
        raise ValueError(f"Defina {PASSWORD_ENV} ou execute num terminal interativo")
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repetir password: "):
        raise ValueError("As passwords não coincidem")
    return password


def _create_user(db: Database, args: argparse.Namespace, out: _Output) -> int:
    try:
        user = UserService(db).create_user(
            email=args.email,
            name=args.name,
            role=Role(args.role),
            password=_read_password(),
            source="cli",
        )
    except EmailAlreadyExistsError:
        raise ValueError(f"Já existe um utilizador com o email {args.email}") from None
    out(f"Utilizador criado: {user.email} ({user.role.value}, id {user.id})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Estado das migrations e índices")
    migrate = commands.add_parser("migrate", help="Aplica migrations pendentes e índices")
    migrate.add_argument("--dry-run", action="store_true", help="Mostra o que seria aplicado")
    commands.add_parser("seed", help="Insere dados iniciais em falta")
    create_user = commands.add_parser("create-user", help="Cria um utilizador ativo")
    create_user.add_argument("--email", required=True)
    create_user.add_argument("--name", required=True)
    create_user.add_argument("--role", choices=[role.value for role in Role], default="admin")
    commands.add_parser(
        "attachments-check", help="Reporta ficheiros de anexos órfãos ou em falta no disco"
    )
    commands.add_parser(
        "report-snapshots", help="Grava o snapshot diário de métricas de cada projeto"
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    client: MongoClient | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    out = _Output(stdout or sys.stdout)
    err = _Output(stderr or sys.stderr)
    settings = settings or get_settings()
    owns_client = client is None
    client = client or mongo.create_client(settings)
    try:
        info = mongo.check_server_compatibility(client)
        out(f"MongoDB {info.version} — base de dados {settings.mongodb_database}")
        db = mongo.get_database(client, settings)
        if args.command == "status":
            return _status(db, settings, out)
        if args.command == "migrate":
            return _migrate(db, settings, out, dry_run=args.dry_run)
        if args.command == "create-user":
            return _create_user(db, args, out)
        if args.command == "attachments-check":
            return _attachments_check(db, settings, out)
        if args.command == "report-snapshots":
            return _report_snapshots(db, out)
        return _seed(db, settings, out)
    except (
        migrations.MigrationError,
        indexes.IndexConflictError,
        mongo.IncompatibleServerError,
        ValueError,
        OSError,
        PyMongoError,
    ) as error:
        err(f"Erro: {error}")
        return 1
    finally:
        if owns_client:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
