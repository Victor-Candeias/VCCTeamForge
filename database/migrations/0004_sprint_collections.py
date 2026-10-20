"""Cria a collection de sprints da fase 3."""

from pymongo.database import Database

DESCRIPTION = "Collection de sprints da fase 3"

COLLECTIONS = ("sprints",)


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
