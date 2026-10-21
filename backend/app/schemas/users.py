"""DTOs da gestão de utilizadores pelo Administrador (DEV-028)."""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from app.core.security import PASSWORD_MAX_LENGTH
from app.domain.permissions import Role
from app.domain.users import UserStatus
from app.schemas.base import ApiModel


class UserCreate(ApiModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserUpdate(ApiModel):
    """Campos omitidos ficam inalterados."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    status: UserStatus | None = None


class PasswordReset(ApiModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserAdminResponse(ApiModel):
    id: str
    email: str
    name: str
    role: Role
    status: UserStatus
    last_login_at: datetime | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "UserAdminResponse":
        return cls(
            id=str(document["_id"]),
            email=document["email"],
            name=document["name"],
            role=Role(document["role"]),
            status=UserStatus(document.get("status", UserStatus.ACTIVE)),
            last_login_at=document.get("lastLoginAt"),
            password_changed_at=document.get("passwordChangedAt"),
            created_at=document["createdAt"],
            updated_at=document.get("updatedAt", document["createdAt"]),
            version=document.get("version", 1),
        )
