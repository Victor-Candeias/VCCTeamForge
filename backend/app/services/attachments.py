"""Anexos de issues: validação, armazenamento, histórico e auditoria (DEV-013)."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.core.errors import (
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.domain.attachments import (
    ALLOWED_TYPES,
    IMAGE_CONTENT_TYPES,
    SIGNATURE_HEAD_BYTES,
    ContentKind,
    allowed_type_for,
    matches_signature,
    sanitize_filename,
)
from app.domain.permissions import Permission
from app.domain.projects import can_manage_project, is_archived
from app.domain.users import User
from app.repositories.attachments import AttachmentRepository
from app.repositories.users import UserRepository
from app.schemas.attachments import Attachment
from app.schemas.auth import UserSummary
from app.services.issue_history import HistoryEvent, IssueActivityRecorder
from app.services.issues import IssueService
from app.storage.attachments import (
    AttachmentStorage,
    FileTooLargeError,
    InvalidStorageKeyError,
    StoredFile,
)

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = ", ".join(sorted(ALLOWED_TYPES))


@dataclass(frozen=True)
class AttachmentContent:
    path: Path
    original_name: str
    content_type: str
    is_image: bool


@dataclass(frozen=True)
class StoredUpload:
    stored: StoredFile
    original_name: str
    content_type: str
    now: datetime


def max_size_label(settings: Settings) -> str:
    return f"{settings.attachments_max_bytes / (1024 * 1024):.0f} MiB"


def store_upload(
    storage: AttachmentStorage,
    settings: Settings,
    project_id: str,
    filename: str | None,
    source: BinaryIO,
) -> StoredUpload:
    """Valida nome, tipo, tamanho e assinatura e grava o ficheiro (partilhado com evidências)."""
    original_name = sanitize_filename(filename)
    if not original_name:
        raise BusinessRuleError("O ficheiro tem de ter nome", field="file")
    allowed = allowed_type_for(original_name)
    if allowed is None:
        raise BusinessRuleError(
            f"Tipo de ficheiro não permitido (aceites: {ALLOWED_EXTENSIONS})", field="file"
        )

    now = datetime.now(UTC)
    try:
        stored = storage.save(
            project_id,
            source,
            max_bytes=settings.attachments_max_bytes,
            now=now,
            head_bytes=SIGNATURE_HEAD_BYTES,
        )
    except FileTooLargeError as error:
        raise PayloadTooLargeError(
            f"O ficheiro excede o máximo de {max_size_label(settings)}", field="file"
        ) from error

    invalid = stored.size == 0 or not matches_signature(allowed.kind, stored.head)
    if allowed.kind is ContentKind.TEXT and stored.has_null_bytes:
        invalid = True
    if invalid:
        storage.delete(stored.storage_key)
        raise BusinessRuleError(
            "O conteúdo do ficheiro não corresponde ao tipo indicado", field="file"
        )
    return StoredUpload(stored, original_name, allowed.content_type, now)


class AttachmentService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.settings = settings
        self.issues = IssueService(db)
        self.attachments = AttachmentRepository(db)
        self.users = UserRepository(db)
        self.storage = AttachmentStorage(settings.attachments_path)
        self.activity = IssueActivityRecorder(db)

    def list_for_issue(self, user: User, issue_id: ObjectId) -> list[Attachment]:
        issue, project = self.issues.get_accessible(user, issue_id)
        return self._to_attachments(user, project, self.attachments.list_for_issue(issue["_id"]))

    def upload(
        self, user: User, issue_id: ObjectId, filename: str | None, source: BinaryIO
    ) -> Attachment:
        issue, project = self.issues.get_accessible(user, issue_id)
        self._ensure_writable(project)
        if (
            self.attachments.count_for_issue(issue["_id"])
            >= self.settings.attachments_max_per_issue
        ):
            raise BusinessRuleError(
                f"A issue já tem o máximo de {self.settings.attachments_max_per_issue} anexos",
                field="file",
            )
        upload = store_upload(
            self.storage, self.settings, str(issue["projectId"]), filename, source
        )
        stored, original_name, now = upload.stored, upload.original_name, upload.now
        document = {
            "issueId": issue["_id"],
            "projectId": issue["projectId"],
            "uploadedBy": user.id,
            "originalName": original_name,
            "storageKey": stored.storage_key,
            "contentType": upload.content_type,
            "size": stored.size,
            "sha256": stored.sha256,
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
            "deletedBy": None,
        }
        try:
            attachment = self.attachments.create(document)
        except PyMongoError:
            # Compensação: sem metadados o ficheiro ficaria órfão no disco.
            self.storage.delete(stored.storage_key)
            raise
        self._record(user, issue, attachment, HistoryEvent.ATTACHMENT_ADDED, "attachment.created")
        return self._to_attachments(user, project, [attachment])[0]

    def get_content(self, user: User, attachment_id: ObjectId) -> AttachmentContent:
        attachment = self._find(attachment_id)
        self.issues.get_accessible(user, attachment["issueId"])
        try:
            path = self.storage.path_for(attachment["storageKey"])
        except InvalidStorageKeyError as error:
            raise NotFoundError("Anexo não encontrado") from error
        if not path.is_file():
            logger.error("Ficheiro do anexo %s em falta no disco", attachment["_id"])
            raise NotFoundError("Anexo não encontrado")
        return AttachmentContent(
            path=path,
            original_name=attachment["originalName"],
            content_type=attachment["contentType"],
            is_image=attachment["contentType"] in IMAGE_CONTENT_TYPES,
        )

    def delete(self, user: User, attachment_id: ObjectId) -> None:
        attachment = self._find(attachment_id)
        issue, project = self.issues.get_accessible(user, attachment["issueId"])
        if not self._can_delete(user, project, attachment):
            raise ForbiddenError(
                "Só quem carregou, o responsável do projeto ou um admin pode remover"
            )
        self._ensure_writable(project)
        if (
            self.attachments.soft_delete(attachment["_id"], actor_id=user.id, now=datetime.now(UTC))
            is None
        ):
            raise NotFoundError("Anexo não encontrado")
        try:
            self.storage.delete(attachment["storageKey"])
        except (OSError, InvalidStorageKeyError):
            logger.exception("Não foi possível apagar o ficheiro do anexo %s", attachment["_id"])
        self._record(user, issue, attachment, HistoryEvent.ATTACHMENT_REMOVED, "attachment.deleted")

    # Auxiliares ----------------------------------------------------------------------------

    def _find(self, attachment_id: ObjectId) -> dict[str, Any]:
        attachment = self.attachments.find_active(attachment_id)
        if attachment is None:
            raise NotFoundError("Anexo não encontrado")
        return attachment

    def _record(
        self,
        user: User,
        issue: dict[str, Any],
        attachment: dict[str, Any],
        event_type: str,
        action: str,
    ) -> None:
        self.activity.record(
            user,
            issue,
            event_type,
            now=datetime.now(UTC),
            audit_action=action,
            audit_entity=("attachment", attachment["_id"]),
            details={
                "attachmentId": str(attachment["_id"]),
                "name": attachment["originalName"],
                "size": attachment["size"],
            },
        )

    @staticmethod
    def _ensure_writable(project: dict[str, Any]) -> None:
        if is_archived(project):
            raise BusinessRuleError("O projeto está arquivado e não pode ser alterado")

    @staticmethod
    def _can_delete(user: User, project: dict[str, Any], attachment: dict[str, Any]) -> bool:
        if not user.has_permissions(Permission.ISSUES_WRITE):
            return False
        return attachment.get("uploadedBy") == user.id or can_manage_project(user, project)

    def _to_attachments(
        self, user: User, project: dict[str, Any], documents: list[dict[str, Any]]
    ) -> list[Attachment]:
        uploaders = self.users.find_by_ids(
            [d["uploadedBy"] for d in documents if d.get("uploadedBy")]
        )
        writable = not is_archived(project)
        result = []
        for document in documents:
            uploader = uploaders.get(document.get("uploadedBy"))
            result.append(
                Attachment(
                    id=str(document["_id"]),
                    issue_id=str(document["issueId"]),
                    original_name=document["originalName"],
                    content_type=document["contentType"],
                    size=document["size"],
                    sha256=document["sha256"],
                    is_image=document["contentType"] in IMAGE_CONTENT_TYPES,
                    uploaded_by=UserSummary.from_document(uploader) if uploader else None,
                    created_at=document["createdAt"],
                    can_delete=writable and self._can_delete(user, project, document),
                )
            )
        return result
