from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from bson import ObjectId

from app.domain.permissions import Permission, Role, permissions_for


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class User:
    id: ObjectId
    email: str
    name: str
    role: Role
    status: UserStatus

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "User":
        return cls(
            id=document["_id"],
            email=document["email"],
            name=document["name"],
            role=Role(document["role"]),
            status=UserStatus(document.get("status", UserStatus.ACTIVE)),
        )

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.role)

    def has_permissions(self, *required: Permission) -> bool:
        return set(required) <= self.permissions
