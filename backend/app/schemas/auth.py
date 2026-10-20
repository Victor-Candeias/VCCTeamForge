from pydantic import BaseModel, Field

from app.core.security import PASSWORD_MAX_LENGTH
from app.domain.permissions import Permission, Role
from app.domain.users import User
from app.schemas.base import ApiModel


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class CsrfTokenResponse(ApiModel):
    csrf_token: str


class CurrentUserResponse(ApiModel):
    id: str
    email: str
    name: str
    role: Role
    permissions: list[Permission]

    @classmethod
    def from_user(cls, user: User) -> "CurrentUserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            permissions=sorted(user.permissions),
        )


class UserSummary(ApiModel):
    id: str
    name: str
    email: str
    role: Role

    @classmethod
    def from_document(cls, document: dict) -> "UserSummary":
        return cls(
            id=str(document["_id"]),
            name=document["name"],
            email=document["email"],
            role=Role(document["role"]),
        )
