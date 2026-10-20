from urllib.parse import quote

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.api.deps import get_app_settings, get_db, require_permissions
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.domain.permissions import Permission
from app.domain.users import User
from app.schemas.attachments import Attachment
from app.services.attachments import AttachmentService

router = APIRouter(tags=["attachments"])

can_read = require_permissions(Permission.ISSUES_READ)
can_write = require_permissions(Permission.ISSUES_WRITE)


def get_attachment_service(
    db: Database = Depends(get_db), settings: Settings = Depends(get_app_settings)
) -> AttachmentService:
    return AttachmentService(db, settings)


def _object_id(value: str, message: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as error:
        raise NotFoundError(message) from error


def content_disposition(disposition: str, filename: str) -> str:
    """``filename`` ASCII de recurso e ``filename*`` (RFC 5987) com o nome original."""
    fallback = "".join(ch if 32 <= ord(ch) < 127 and ch not in '"\\' else "_" for ch in filename)
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.get("/issues/{issue_id}/attachments", response_model=list[Attachment])
def list_attachments(
    issue_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: AttachmentService = Depends(get_attachment_service),
) -> list[Attachment]:
    response.headers["Cache-Control"] = "no-store"
    return service.list_for_issue(user, _object_id(issue_id, "Issue não encontrada"))


@router.post(
    "/issues/{issue_id}/attachments",
    response_model=Attachment,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment(
    issue_id: str,
    file: UploadFile = File(...),
    user: User = Depends(can_write),
    service: AttachmentService = Depends(get_attachment_service),
) -> Attachment:
    return service.upload(
        user, _object_id(issue_id, "Issue não encontrada"), file.filename, file.file
    )


@router.get("/attachments/{attachment_id}/content")
def download_attachment(
    attachment_id: str,
    inline: bool = Query(default=False),
    user: User = Depends(can_read),
    service: AttachmentService = Depends(get_attachment_service),
) -> FileResponse:
    content = service.get_content(user, _object_id(attachment_id, "Anexo não encontrado"))
    disposition = "inline" if inline and content.is_image else "attachment"
    return FileResponse(
        content.path,
        media_type=content.content_type,
        headers={
            "Content-Disposition": content_disposition(disposition, content.original_name),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: str,
    user: User = Depends(can_write),
    service: AttachmentService = Depends(get_attachment_service),
) -> Response:
    service.delete(user, _object_id(attachment_id, "Anexo não encontrado"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
