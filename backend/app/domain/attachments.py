"""Regras de validação de anexos: lista branca de tipos, assinaturas e nomes (DEV-013)."""

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

ORIGINAL_NAME_MAX_LENGTH = 200


class ContentKind(StrEnum):
    PNG = "png"
    JPEG = "jpeg"
    GIF = "gif"
    WEBP = "webp"
    PDF = "pdf"
    ZIP = "zip"
    TEXT = "text"


@dataclass(frozen=True)
class AllowedType:
    content_type: str
    kind: ContentKind

    @property
    def is_image(self) -> bool:
        return self.kind in IMAGE_KINDS


IMAGE_KINDS = frozenset({ContentKind.PNG, ContentKind.JPEG, ContentKind.GIF, ContentKind.WEBP})

ALLOWED_TYPES: dict[str, AllowedType] = {
    "png": AllowedType("image/png", ContentKind.PNG),
    "jpg": AllowedType("image/jpeg", ContentKind.JPEG),
    "jpeg": AllowedType("image/jpeg", ContentKind.JPEG),
    "gif": AllowedType("image/gif", ContentKind.GIF),
    "webp": AllowedType("image/webp", ContentKind.WEBP),
    "pdf": AllowedType("application/pdf", ContentKind.PDF),
    "txt": AllowedType("text/plain", ContentKind.TEXT),
    "log": AllowedType("text/plain", ContentKind.TEXT),
    "md": AllowedType("text/markdown", ContentKind.TEXT),
    "csv": AllowedType("text/csv", ContentKind.TEXT),
    "json": AllowedType("application/json", ContentKind.TEXT),
    "zip": AllowedType("application/zip", ContentKind.ZIP),
    "docx": AllowedType(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ContentKind.ZIP,
    ),
    "xlsx": AllowedType(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ContentKind.ZIP
    ),
    "pptx": AllowedType(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ContentKind.ZIP,
    ),
}

IMAGE_CONTENT_TYPES = frozenset(t.content_type for t in ALLOWED_TYPES.values() if t.is_image)

# Bytes necessários no início do ficheiro para verificar as assinaturas.
SIGNATURE_HEAD_BYTES = 16


def allowed_type_for(filename: str) -> AllowedType | None:
    suffix = PurePosixPath(filename).suffix.lower().lstrip(".")
    return ALLOWED_TYPES.get(suffix)


def matches_signature(kind: ContentKind, head: bytes) -> bool:
    """Confirma os "magic bytes"; ficheiros de texto são verificados à parte (bytes nulos)."""
    match kind:
        case ContentKind.PNG:
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        case ContentKind.JPEG:
            return head.startswith(b"\xff\xd8\xff")
        case ContentKind.GIF:
            return head.startswith((b"GIF87a", b"GIF89a"))
        case ContentKind.WEBP:
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        case ContentKind.PDF:
            return head.startswith(b"%PDF-")
        case ContentKind.ZIP:
            return head.startswith((b"PK\x03\x04", b"PK\x05\x06"))
        case ContentKind.TEXT:
            return True


def sanitize_filename(name: str | None) -> str:
    """Nome a apresentar: sem diretórios, caracteres de controlo nem espaços nas pontas."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = unicodedata.normalize("NFC", base)
    cleaned = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C").strip(" .")
    if not cleaned:
        return ""
    if len(cleaned) <= ORIGINAL_NAME_MAX_LENGTH:
        return cleaned
    path = PurePosixPath(cleaned)
    suffix = path.suffix if len(path.suffix) <= 10 else ""
    return path.stem[: ORIGINAL_NAME_MAX_LENGTH - len(suffix)] + suffix
