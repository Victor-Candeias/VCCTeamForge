"""Seeds em ``database/seed/<collection>.json`` (``{"documents": [{"_id": ...}, ...]}``).

Cada documento só é inserido se ainda não existir (``$setOnInsert``): reexecutar é seguro e nunca
sobrepõe alterações feitas pela Administração.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from pymongo.database import Database

SEED_DIR = Path("seed")


class SeedFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    documents: list[dict[str, Any]]

    @field_validator("documents")
    @classmethod
    def _require_ids(cls, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = [document.get("_id") for document in documents]
        if any(document_id is None for document_id in ids):
            raise ValueError("todos os documentos de seed precisam de _id")
        if len(set(map(repr, ids))) != len(ids):
            raise ValueError("_id repetido no seed")
        return documents


@dataclass(frozen=True)
class SeedResult:
    collection: str
    inserted: int
    existing: int


def load_seeds(database_dir: Path) -> dict[str, list[dict[str, Any]]]:
    seeds = {}
    for path in sorted((database_dir / SEED_DIR).glob("*.json")):
        content = json.loads(path.read_text(encoding="utf-8"))
        seeds[path.stem] = SeedFile.model_validate(content).documents
    return seeds


def apply_seeds(db: Database, seeds: dict[str, list[dict[str, Any]]]) -> list[SeedResult]:
    results = []
    for collection, documents in seeds.items():
        inserted = 0
        for document in documents:
            fields = {key: value for key, value in document.items() if key != "_id"}
            now = datetime.now(UTC)
            result = db[collection].update_one(
                {"_id": document["_id"]},
                {"$setOnInsert": {**fields, "createdAt": now, "updatedAt": now}},
                upsert=True,
            )
            inserted += result.upserted_id is not None
        results.append(SeedResult(collection, inserted, len(documents) - inserted))
    return results
