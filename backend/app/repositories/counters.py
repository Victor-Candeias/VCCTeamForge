from pymongo import ReturnDocument

from app.repositories.base import MongoRepository


class CounterRepository(MongoRepository):
    """Sequências atómicas (ex.: número de issue por projeto) com ``$inc``.

    Nunca usar contagem de documentos para gerar números sequenciais.
    """

    collection_name = "counters"

    def next_value(self, name: str) -> int:
        document = self.collection.find_one_and_update(
            {"_id": name},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(document["value"])
