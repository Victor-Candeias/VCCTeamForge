"""Cria a collection de snapshots de relatório da fase 5."""

from pymongo.database import Database

DESCRIPTION = "Collection de snapshots de relatório da fase 5"

COLLECTIONS = ("report_snapshots",)


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
