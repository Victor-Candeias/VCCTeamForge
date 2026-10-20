"""Cria as collections de casos e planos de teste da fase 4."""

from pymongo.database import Database

DESCRIPTION = "Collections de casos e planos de teste da fase 4"

COLLECTIONS = ("test_cases", "test_plans")


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
