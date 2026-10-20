from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.repositories.base import MongoRepository


class ProjectKeyExistsError(Exception):
    pass


class ProjectRepository(MongoRepository):
    collection_name = "projects"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            document["_id"] = self.collection.insert_one(document).inserted_id
        except DuplicateKeyError as error:
            raise ProjectKeyExistsError(document.get("key")) from error
        return document

    def find_by_id(self, project_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": project_id})

    def search(
        self,
        query: dict[str, Any],
        *,
        sort: list[tuple[str, int]],
        skip: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return list(self.collection.find(query).sort(sort).skip(skip).limit(limit))

    def count(self, query: dict[str, Any]) -> int:
        return self.collection.count_documents(query)

    def update_versioned(
        self,
        project_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any] | None = None,
        add_member: ObjectId | None = None,
        remove_member: ObjectId | None = None,
    ) -> dict[str, Any] | None:
        """Aplica a alteração só se ``version`` coincidir (controlo otimista).

        Devolve o documento atualizado ou ``None`` se o projeto não existir ou a versão divergir.
        """
        update: dict[str, Any] = {
            "$set": {**(set_fields or {}), "updatedAt": now},
            "$inc": {"version": 1},
        }
        if add_member is not None:
            update["$addToSet"] = {"memberIds": add_member}
        if remove_member is not None:
            update["$pull"] = {"memberIds": remove_member}
        return self.collection.find_one_and_update(
            {"_id": project_id, "version": version},
            update,
            return_document=ReturnDocument.AFTER,
        )
