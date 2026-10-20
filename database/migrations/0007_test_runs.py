"""Cria a collection de execuções de testes da fase 4."""

from pymongo.database import Database

DESCRIPTION = "Collection de execuções de testes da fase 4"

COLLECTIONS = ("test_runs",)


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
