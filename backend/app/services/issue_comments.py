"""Comentários e consulta do histórico de issues (DEV-012)."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ForbiddenError, NotFoundError
from app.domain.projects import can_manage_project, is_archived
from app.domain.users import User
from app.repositories.issue_comments import IssueCommentRepository
from app.repositories.issue_history import IssueHistoryRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserSummary
from app.schemas.comments import Comment
from app.schemas.common import PageParams
from app.schemas.history import FieldChange, HistoryEvent
from app.services.issue_history import HistoryEvent as EventType
from app.services.issue_history import IssueActivityRecorder
from app.services.issues import IssueService


class IssueCommentService:
    def __init__(self, db: Database) -> None:
        self.issues = IssueService(db)
        self.comments = IssueCommentRepository(db)
        self.history = IssueHistoryRepository(db)
        self.users = UserRepository(db)
        self.activity = IssueActivityRecorder(db)

    # Comentários ---------------------------------------------------------------------------

    def list_comments(
        self, user: User, issue_id: ObjectId, page: PageParams
    ) -> tuple[list[Comment], int]:
        issue, project = self.issues.get_accessible(user, issue_id)
        documents = self.comments.list_page(issue["_id"], skip=page.skip, limit=page.page_size)
        return self._to_comments(user, project, documents), self.comments.count(issue["_id"])

    def create(self, user: User, issue_id: ObjectId, body: str) -> Comment:
        issue, project = self.issues.get_accessible(user, issue_id)
        self._ensure_writable(project)
        now = datetime.now(UTC)
        comment = self.comments.create(
            {
                "issueId": issue["_id"],
                "projectId": issue["projectId"],
                "authorId": user.id,
                "body": self._clean_body(body),
                "createdAt": now,
                "updatedAt": now,
                "editedAt": None,
                "deletedAt": None,
                "deletedBy": None,
            }
        )
        self._record(user, issue, comment, EventType.COMMENT_ADDED, "comment.created", now)
        return self._to_comments(user, project, [comment])[0]

    def update(self, user: User, issue_id: ObjectId, comment_id: ObjectId, body: str) -> Comment:
        issue, project, comment = self._get_comment(user, issue_id, comment_id)
        if comment.get("authorId") != user.id:
            raise ForbiddenError("Só o autor pode editar o comentário")
        self._ensure_writable(project)
        now = datetime.now(UTC)
        updated = self.comments.update_body(comment["_id"], self._clean_body(body), now=now)
        if updated is None:
            raise NotFoundError("Comentário não encontrado")
        self._record(user, issue, updated, EventType.COMMENT_EDITED, "comment.updated", now)
        return self._to_comments(user, project, [updated])[0]

    def delete(self, user: User, issue_id: ObjectId, comment_id: ObjectId) -> None:
        issue, project, comment = self._get_comment(user, issue_id, comment_id)
        if not self._can_delete(user, project, comment):
            raise ForbiddenError("Só o autor, o responsável do projeto ou um admin pode remover")
        self._ensure_writable(project)
        now = datetime.now(UTC)
        if self.comments.soft_delete(comment["_id"], actor_id=user.id, now=now) is None:
            raise NotFoundError("Comentário não encontrado")
        self._record(user, issue, comment, EventType.COMMENT_DELETED, "comment.deleted", now)

    # Histórico -----------------------------------------------------------------------------

    def history_page(
        self, user: User, issue_id: ObjectId, page: PageParams
    ) -> tuple[list[HistoryEvent], int]:
        issue, _ = self.issues.get_accessible(user, issue_id)
        documents = self.history.list_page(issue["_id"], skip=page.skip, limit=page.page_size)
        actors = self.users.find_by_ids([d["actorId"] for d in documents if d.get("actorId")])
        events = [
            HistoryEvent(
                id=str(document["_id"]),
                type=document["type"],
                actor=self._summary(actors.get(document.get("actorId"))),
                changes=[FieldChange.model_validate(c) for c in document.get("changes", [])],
                details=document.get("details", {}),
                created_at=document["createdAt"],
            )
            for document in documents
        ]
        return events, self.history.count(issue["_id"])

    # Auxiliares ----------------------------------------------------------------------------

    def _get_comment(
        self, user: User, issue_id: ObjectId, comment_id: ObjectId
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        issue, project = self.issues.get_accessible(user, issue_id)
        comment = self.comments.find_for_issue(issue["_id"], comment_id)
        if comment is None or comment.get("deletedAt") is not None:
            raise NotFoundError("Comentário não encontrado")
        return issue, project, comment

    def _record(
        self,
        user: User,
        issue: dict[str, Any],
        comment: dict[str, Any],
        event_type: str,
        action: str,
        now: datetime,
    ) -> None:
        self.activity.record(
            user,
            issue,
            event_type,
            now=now,
            audit_action=action,
            audit_entity=("comment", comment["_id"]),
            details={"commentId": str(comment["_id"])},
        )

    @staticmethod
    def _clean_body(body: str) -> str:
        cleaned = body.strip()
        if not cleaned:
            raise BusinessRuleError("O comentário não pode estar vazio", field="body")
        return cleaned

    @staticmethod
    def _ensure_writable(project: dict[str, Any]) -> None:
        if is_archived(project):
            raise BusinessRuleError("O projeto está arquivado e não pode ser alterado")

    @staticmethod
    def _can_delete(user: User, project: dict[str, Any], comment: dict[str, Any]) -> bool:
        return comment.get("authorId") == user.id or can_manage_project(user, project)

    @staticmethod
    def _summary(document: dict[str, Any] | None) -> UserSummary | None:
        return UserSummary.from_document(document) if document else None

    def _to_comments(
        self, user: User, project: dict[str, Any], documents: list[dict[str, Any]]
    ) -> list[Comment]:
        authors = self.users.find_by_ids([d["authorId"] for d in documents if d.get("authorId")])
        writable = not is_archived(project)
        result = []
        for document in documents:
            deleted = document.get("deletedAt") is not None
            result.append(
                Comment(
                    id=str(document["_id"]),
                    issue_id=str(document["issueId"]),
                    author=self._summary(authors.get(document.get("authorId"))),
                    body=None if deleted else document.get("body"),
                    deleted=deleted,
                    created_at=document["createdAt"],
                    edited_at=document.get("editedAt"),
                    deleted_at=document.get("deletedAt"),
                    can_edit=writable and not deleted and document.get("authorId") == user.id,
                    can_delete=writable
                    and not deleted
                    and self._can_delete(user, project, document),
                )
            )
        return result
