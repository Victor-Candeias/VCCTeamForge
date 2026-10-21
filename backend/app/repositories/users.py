import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.domain.permissions import Role
from app.domain.users import UserStatus, normalize_email
from app.repositories.base import MongoRepository


class EmailAlreadyExistsError(Exception):
    pass


_PUBLIC_PROJECTION = {"passwordHash": 0}


class UserRepository(MongoRepository):
    collection_name = "users"

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        return self.collection.find_one({"normalizedEmail": normalize_email(email)})

    def find_by_id(self, user_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": user_id}, _PUBLIC_PROJECTION)

    def find_by_ids(self, user_ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        if not user_ids:
            return {}
        cursor = self.collection.find({"_id": {"$in": list(set(user_ids))}}, _PUBLIC_PROJECTION)
        return {document["_id"]: document for document in cursor}

    def search_active(self, text: str, limit: int) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"status": UserStatus.ACTIVE.value}
        if text.strip():
            pattern = re.escape(text.strip())
            query["$or"] = [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"normalizedEmail": {"$regex": pattern, "$options": "i"}},
            ]
        return list(self.collection.find(query, _PUBLIC_PROJECTION).sort("name", 1).limit(limit))

    def search(
        self, query: dict[str, Any], *, sort: list[tuple[str, int]], skip: int, limit: int
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find(query, _PUBLIC_PROJECTION).sort(sort).skip(skip)
        return list(cursor.limit(limit))

    def count(self, query: dict[str, Any]) -> int:
        return self.collection.count_documents(query)

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

    def update_versioned(
        self, user_id: ObjectId, version: int, *, now: datetime, set_fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Aplica a alteração só se ``version`` coincidir (controlo otimista).

        Devolve o documento atualizado ou ``None`` se não existir ou a versão divergir. Lança
        ``EmailAlreadyExistsError`` se o novo email já estiver em uso.
        """
        changes = dict(set_fields)
        if "email" in changes:
            changes["email"] = changes["email"].strip()
            changes["normalizedEmail"] = normalize_email(changes["email"])
        try:
            return self.collection.find_one_and_update(
                {"_id": user_id, "version": version},
                {"$set": {**changes, "updatedAt": now}, "$inc": {"version": 1}},
                projection=_PUBLIC_PROJECTION,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as error:
            raise EmailAlreadyExistsError(changes.get("email", "")) from error
