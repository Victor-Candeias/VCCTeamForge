"""Consulta dos registos de auditoria (``audit:read``)."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError
from app.repositories.audit import AuditLogRepository
from app.repositories.users import UserRepository
from app.schemas.audit import AuditLog
from app.schemas.auth import UserSummary
from app.schemas.common import PageParams


def build_audit_filter(
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if entity_type:
        query["entityType"] = entity_type
    if entity_id:
        # O ID da entidade pode estar guardado como ObjectId ou como texto.
        values: list[Any] = [entity_id]
        if ObjectId.is_valid(entity_id):
            values.append(ObjectId(entity_id))
        query["entityId"] = {"$in": values}
    if actor_id:
        if not ObjectId.is_valid(actor_id):
            raise BusinessRuleError("Identificador inválido", field="actorId")
        query["actorId"] = ObjectId(actor_id)
    if action:
        query["action"] = action
    if date_from and date_to and date_to < date_from:
        raise BusinessRuleError("O fim do intervalo é anterior ao início", field="to")
    created: dict[str, datetime] = {}
    if date_from:
        created["$gte"] = datetime.combine(date_from, time.min, tzinfo=UTC)
    if date_to:
        created["$lt"] = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
    if created:
        query["createdAt"] = created
    return query


class AuditService:
    def __init__(self, db: Database) -> None:
        self.audit = AuditLogRepository(db)
        self.users = UserRepository(db)

    def search(self, query: dict[str, Any], page: PageParams) -> tuple[list[AuditLog], int]:
        documents = self.audit.search(query, skip=page.skip, limit=page.page_size)
        actors = self.users.find_by_ids([d["actorId"] for d in documents if d.get("actorId")])
        items = []
        for document in documents:
            actor = actors.get(document.get("actorId"))
            entity_id = document.get("entityId")
            items.append(
                AuditLog(
                    id=str(document["_id"]),
                    action=document["action"],
                    actor=UserSummary.from_document(actor) if actor else None,
                    entity_type=document.get("entityType"),
                    entity_id=str(entity_id) if entity_id is not None else None,
                    ip=document.get("ip"),
                    request_id=document.get("requestId"),
                    details=document.get("details") or {},
                    created_at=document["createdAt"],
                )
            )
        return items, self.audit.count(query)
