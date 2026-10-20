"""Atribui ``rank`` (ordem manual do backlog/quadro) às issues que ainda não o têm."""

from pymongo import ASCENDING, DESCENDING, UpdateOne
from pymongo.database import Database

DESCRIPTION = "Ordem manual (rank) das issues existentes"

RANK_STEP = 1024.0


def up(db: Database) -> None:
    issues = db["issues"]
    for project_id in issues.distinct("projectId", {"rank": None}):
        last = issues.find_one(
            {"projectId": project_id, "rank": {"$ne": None}},
            {"rank": 1},
            sort=[("rank", DESCENDING)],
        )
        start = float(last["rank"]) if last else 0.0
        missing = issues.find({"projectId": project_id, "rank": None}, {"_id": 1}).sort(
            "number", ASCENDING
        )
        operations = [
            UpdateOne({"_id": doc["_id"]}, {"$set": {"rank": start + (index + 1) * RANK_STEP}})
            for index, doc in enumerate(missing)
        ]
        if operations:
            issues.bulk_write(operations, ordered=False)
