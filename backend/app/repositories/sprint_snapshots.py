from typing import Any

from bson import ObjectId

from app.repositories.base import MongoRepository


class SprintSnapshotRepository(MongoRepository):
    """Fotografias do âmbito de um sprint (compromisso, diárias e fecho)."""

    collection_name = "sprint_snapshots"

    def save(self, document: dict[str, Any]) -> None:
        """Grava (ou substitui) o snapshot do sprint para o ``kind`` e ``day`` indicados."""
        key = {"sprintId": document["sprintId"], "kind": document["kind"], "day": document["day"]}
        self.collection.replace_one(key, document, upsert=True)

    def find_latest(self, sprint_id: ObjectId, kind: str) -> dict[str, Any] | None:
        return self.collection.find_one({"sprintId": sprint_id, "kind": kind}, sort=[("day", -1)])

    def find_all(self, sprint_id: ObjectId, kind: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"sprintId": sprint_id, "kind": kind}).sort("day", 1))

    def find_totals(self, sprint_id: ObjectId, kinds: list[str]) -> list[dict[str, Any]]:
        """Só ``kind``, ``day`` e ``totals`` (sem as issues), por dia e ``takenAt``."""
        return list(
            self.collection.find(
                {"sprintId": sprint_id, "kind": {"$in": kinds}},
                {"kind": 1, "day": 1, "takenAt": 1, "totals": 1},
            ).sort([("day", 1), ("takenAt", 1)])
        )
