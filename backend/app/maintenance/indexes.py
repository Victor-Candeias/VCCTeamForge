"""Aplicação idempotente dos índices declarados em ``database/indexes/indexes.json``."""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pymongo.database import Database

INDEXES_FILE = Path("indexes") / "indexes.json"

# Opções comparadas para decidir se um índice existente corresponde à definição.
COMPARED_OPTIONS = ("unique", "sparse", "expireAfterSeconds", "partialFilterExpression")


class IndexOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unique: bool = False
    sparse: bool = False
    expireAfterSeconds: int | None = Field(default=None, ge=0)
    partialFilterExpression: dict[str, Any] | None = None

    def normalized(self) -> dict[str, Any]:
        return self.model_dump(exclude_defaults=True)


class IndexSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    keys: list[tuple[str, Literal[1, -1]]] = Field(min_length=1)
    options: IndexOptions = Field(default_factory=IndexOptions)


class IndexFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    indexes: list[IndexSpec]


class IndexAction(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    EXISTS_WITH_OTHER_NAME = "exists_with_other_name"
    PENDING = "pending"


@dataclass(frozen=True)
class IndexResult:
    spec: IndexSpec
    action: IndexAction
    existing_name: str | None = None


class IndexConflictError(RuntimeError):
    pass


def load_index_specs(database_dir: Path) -> list[IndexSpec]:
    path = database_dir / INDEXES_FILE
    specs = IndexFile.model_validate(json.loads(path.read_text(encoding="utf-8"))).indexes
    seen: set[tuple[str, str]] = set()
    for spec in specs:
        identity = (spec.collection, spec.name)
        if identity in seen:
            raise ValueError(f"Índice duplicado em {path}: {spec.collection}.{spec.name}")
        seen.add(identity)
    return specs


def _normalize_keys(keys: Any) -> list[tuple[str, int]]:
    return [(field, int(direction)) for field, direction in keys]


def _existing_options(info: dict[str, Any]) -> dict[str, Any]:
    options = {name: info[name] for name in COMPARED_OPTIONS if name in info}
    if "expireAfterSeconds" in options:
        options["expireAfterSeconds"] = int(options["expireAfterSeconds"])
    return IndexOptions.model_validate(options).normalized()


def _plan(spec: IndexSpec, existing: dict[str, dict[str, Any]]) -> IndexResult:
    keys = _normalize_keys(spec.keys)
    options = spec.options.normalized()
    current = existing.get(spec.name)
    if current is not None:
        if _normalize_keys(current["key"]) == keys and _existing_options(current) == options:
            return IndexResult(spec, IndexAction.UNCHANGED)
        raise IndexConflictError(
            f"O índice {spec.collection}.{spec.name} existe com outra definição; "
            "crie uma migration que o remova antes de o redefinir."
        )
    for name, info in existing.items():
        if _normalize_keys(info["key"]) == keys:
            if _existing_options(info) == options:
                return IndexResult(spec, IndexAction.EXISTS_WITH_OTHER_NAME, existing_name=name)
            raise IndexConflictError(
                f"Já existe o índice {spec.collection}.{name} com as mesmas chaves de "
                f"{spec.name} mas opções diferentes."
            )
    return IndexResult(spec, IndexAction.PENDING)


def ensure_indexes(
    db: Database, specs: list[IndexSpec], *, dry_run: bool = False
) -> list[IndexResult]:
    """Cria os índices em falta. Valida todos antes de criar qualquer um."""
    existing_by_collection: dict[str, dict[str, dict[str, Any]]] = {}
    collections = set(db.list_collection_names())
    for collection in {spec.collection for spec in specs}:
        existing_by_collection[collection] = (
            db[collection].index_information() if collection in collections else {}
        )

    plan = [_plan(spec, existing_by_collection[spec.collection]) for spec in specs]
    if dry_run:
        return plan

    results = []
    for result in plan:
        if result.action is IndexAction.PENDING:
            spec = result.spec
            db[spec.collection].create_index(spec.keys, name=spec.name, **spec.options.normalized())
            result = IndexResult(spec, IndexAction.CREATED)
        results.append(result)
    return results
