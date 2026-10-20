from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.repositories.base import MongoRepository


class SprintNameExistsError(Exception):
    pass


class SprintRepository(MongoRepository):
    collection_name = "sprints"

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            document["_id"] = self.collection.insert_one(document).inserted_id
        except DuplicateKeyError as error:
            raise SprintNameExistsError(document.get("name")) from error
        return document

    def find_by_id(self, sprint_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": sprint_id})

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

    def find_overlapping(
        self,
        project_id: ObjectId,
        *,
        start: datetime,
        end: datetime,
        statuses: list[str],
        exclude_id: ObjectId | None = None,
    ) -> dict[str, Any] | None:
        """Primeiro sprint do projeto, nos estados indicados, que interseta [start, end]."""
        query: dict[str, Any] = {
            "projectId": project_id,
            "status": {"$in": statuses},
            "startDate": {"$lte": end},
            "endDate": {"$gte": start},
        }
        if exclude_id is not None:
            query["_id"] = {"$ne": exclude_id}
        return self.collection.find_one(query, sort=[("startDate", 1)])

    def update_versioned(
        self,
        sprint_id: ObjectId,
        version: int,
        *,
        now: datetime,
        set_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Aplica a alteração só se ``version`` coincidir (controlo otimista).

        Devolve o documento atualizado ou ``None`` se o sprint não existir ou a versão divergir.
        """
        try:
            return self.collection.find_one_and_update(
                {"_id": sprint_id, "version": version},
                {"$set": {**set_fields, "updatedAt": now}, "$inc": {"version": 1}},
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as error:
            raise SprintNameExistsError(set_fields.get("name")) from error
