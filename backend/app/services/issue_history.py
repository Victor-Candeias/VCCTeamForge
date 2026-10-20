"""Histórico de issues e auditoria das mutações (DEV-012)."""

import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.logging import request_id_var
from app.domain.users import User
from app.repositories.audit import AuditLogRepository
from app.repositories.issue_history import IssueHistoryRepository
from app.services.common import jsonable

logger = logging.getLogger(__name__)

# Campos longos: o histórico regista apenas que mudaram (sem copiar o conteúdo).
CONTENT_ONLY_FIELDS = frozenset({"description", "acceptanceCriteria"})


class HistoryEvent:
    CREATED = "created"
    UPDATED = "updated"
    COMMENT_ADDED = "comment_added"
    COMMENT_EDITED = "comment_edited"
    COMMENT_DELETED = "comment_deleted"
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_REMOVED = "attachment_removed"


def diff_issue(
    before: dict[str, Any], changes: dict[str, Any], fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Lista ``[{field, from, to}]`` só com os campos de ``fields`` que mudam de valor."""
    diff: list[dict[str, Any]] = []
    for field in fields:
        if field not in changes or before.get(field) == changes[field]:
            continue
        if field in CONTENT_ONLY_FIELDS:
            diff.append({"field": field, "from": None, "to": None})
        else:
            diff.append(
                {
                    "field": field,
                    "from": jsonable(before.get(field)),
                    "to": jsonable(changes[field]),
                }
            )
    return diff


class IssueActivityRecorder:
    """Escreve histórico e auditoria depois da mutação.

    Sem transações (MongoDB 4.4 standalone): se a escrita falhar, a mutação já foi aplicada,
    por isso regista-se o erro no log (com ``requestId``) e a resposta mantém-se.
    """

    def __init__(self, db: Database) -> None:
        self.history = IssueHistoryRepository(db)
        self.audit = AuditLogRepository(db)

    def record(
        self,
        user: User,
        issue: dict[str, Any],
        event_type: str,
        *,
        now: datetime,
        audit_action: str | None = None,
        audit_entity: tuple[str, ObjectId] | None = None,
        changes: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.history.record(
                issue_id=issue["_id"],
                project_id=issue["projectId"],
                actor_id=user.id,
                event_type=event_type,
                now=now,
                changes=changes,
                details=details,
            )
        except PyMongoError:
            logger.exception(
                "Falha ao gravar histórico da issue %s (requestId=%s)",
                issue["_id"],
                request_id_var.get(),
            )
        if audit_action is None:
            return
        entity_type, entity_id = audit_entity or ("issue", issue["_id"])
        try:
            self.audit.record(
                audit_action,
                now=now,
                actor_id=user.id,
                entity_type=entity_type,
                entity_id=entity_id,
                details={
                    "issueId": str(issue["_id"]),
                    "issueKey": issue.get("key"),
                    "projectId": str(issue["projectId"]),
                    **({"changes": changes} if changes else {}),
                    **(details or {}),
                },
            )
        except PyMongoError:
            logger.exception(
                "Falha ao gravar auditoria %s (requestId=%s)", audit_action, request_id_var.get()
            )
