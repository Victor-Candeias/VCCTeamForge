from pymongo.collection import Collection
from pymongo.database import Database


class MongoRepository:
    """Base para repositórios: cada subclasse indica a sua collection."""

    collection_name: str

    def __init__(self, database: Database) -> None:
        self.collection: Collection = database[self.collection_name]
