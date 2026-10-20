from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.domain.permissions import Role
from app.domain.users import UserStatus, normalize_email
from app.repositories.base import MongoRepository


class EmailAlreadyExistsError(Exception):
    pass


class UserRepository(MongoRepository):
    collection_name = "users"

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        return self.collection.find_one({"normalizedEmail": normalize_email(email)})

    def find_by_id(self, user_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": user_id}, {"passwordHash": 0})

    def create(
        self, *, email: str, name: str, role: Role, password_hash: str, now: datetime
    ) -> dict[str, Any]:
        document = {
            "email": email.strip(),
            "normalizedEmail": normalize_email(email),
            "name": name.strip(),
            "role": role.value,
            "status": UserStatus.ACTIVE.value,
            "passwordHash": password_hash,
            "passwordChangedAt": now,
            "lastLoginAt": None,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        try:
            document["_id"] = self.collection.insert_one(document).inserted_id
        except DuplicateKeyError as error:
            raise EmailAlreadyExistsError(email) from error
        return document

    def record_login(
        self, user_id: ObjectId, now: datetime, new_password_hash: str | None = None
    ) -> None:
        changes: dict[str, Any] = {"lastLoginAt": now}
        if new_password_hash:
            changes["passwordHash"] = new_password_hash
        self.collection.update_one({"_id": user_id}, {"$set": changes})
