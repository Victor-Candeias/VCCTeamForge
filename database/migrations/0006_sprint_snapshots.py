"""Cria a collection de snapshots de sprint (compromisso, diários e fecho)."""

from pymongo.database import Database

DESCRIPTION = "Collection de snapshots de sprint da fase 3"

COLLECTIONS = ("sprint_snapshots",)


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
