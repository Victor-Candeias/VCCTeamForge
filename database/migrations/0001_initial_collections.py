"""Cria as collections da fase 1 (README §5.1) e as de suporte à autenticação."""

from pymongo.database import Database

DESCRIPTION = "Collections iniciais da fase 1"

COLLECTIONS = (
    "users",
    "teams",
    "projects",
    "counters",
    "audit_logs",
    "settings",
    "sessions",
    "login_attempts",
)


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
