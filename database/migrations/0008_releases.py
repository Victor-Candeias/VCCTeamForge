"""Cria a collection de releases da fase 4."""

from pymongo.database import Database

DESCRIPTION = "Collection de releases da fase 4"

COLLECTIONS = ("releases",)


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
