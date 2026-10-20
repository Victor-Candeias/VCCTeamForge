"""Cria as collections da fase 2 (issues, comentários, histórico e anexos)."""

from pymongo.database import Database

DESCRIPTION = "Collections de issues da fase 2"

COLLECTIONS = ("issues", "issue_comments", "issue_history", "attachments")


def up(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
