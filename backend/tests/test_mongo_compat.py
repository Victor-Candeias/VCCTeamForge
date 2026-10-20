"""Testes de compatibilidade com o servidor MongoDB real (4.4).

Validam as funcionalidades de que a aplicação depende. Correr sempre antes de atualizar o PyMongo:
VCCTF_REQUIRE_MONGO=1 VCCTF_TEST_MONGODB_PORT=27017 pytest tests/test_mongo_compat.py
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.repositories import mongo
from app.repositories.counters import CounterRepository


def test_server_version_is_supported(mongo_client: MongoClient) -> None:
    info = mongo.check_server_compatibility(mongo_client)

    assert info.version_tuple[:2] >= (4, 4)


def test_round_trip_preserves_object_id_and_utc_datetime(db: Database) -> None:
    created_at = datetime(2026, 10, 20, 9, 0, 0, 123000, tzinfo=UTC)
    owner_id = ObjectId()

    inserted = db.projects.insert_one(
        {"key": "DVC", "leadUserId": owner_id, "createdAt": created_at}
    )
    document = db.projects.find_one({"_id": inserted.inserted_id})

    assert document["leadUserId"] == owner_id
    assert document["createdAt"] == created_at
    assert document["createdAt"].utcoffset().total_seconds() == 0


def test_counter_increments_are_atomic_under_concurrency(db: Database) -> None:
    counters = CounterRepository(db)

    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: counters.next_value("issues:DVC"), range(200)))

    assert sorted(values) == list(range(1, 201))


def test_unique_index_rejects_duplicates(db: Database) -> None:
    db.users.create_index([("normalizedEmail", ASCENDING)], unique=True)
    db.users.insert_one({"normalizedEmail": "ana@example.pt"})

    with pytest.raises(DuplicateKeyError):
        db.users.insert_one({"normalizedEmail": "ana@example.pt"})


def test_create_index_is_idempotent(db: Database) -> None:
    first = db.issues.create_index([("projectId", 1), ("number", 1)], unique=True)
    second = db.issues.create_index([("projectId", 1), ("number", 1)], unique=True)

    assert first == second


def test_ttl_and_partial_indexes_are_supported(db: Database) -> None:
    db.sessions.create_index("expiresAt", expireAfterSeconds=0)
    db.issues.create_index(
        [("assigneeId", 1)], partialFilterExpression={"assigneeId": {"$exists": True}}
    )

    ttl = db.sessions.index_information()["expiresAt_1"]
    assert ttl["expireAfterSeconds"] == 0


def test_optimistic_concurrency_with_version_field(db: Database) -> None:
    issue_id = db.issues.insert_one({"title": "A", "version": 1}).inserted_id

    first = db.issues.update_one(
        {"_id": issue_id, "version": 1}, {"$set": {"title": "B"}, "$inc": {"version": 1}}
    )
    stale = db.issues.update_one(
        {"_id": issue_id, "version": 1}, {"$set": {"title": "C"}, "$inc": {"version": 1}}
    )

    assert first.modified_count == 1
    assert stale.matched_count == 0
    assert db.issues.find_one({"_id": issue_id})["title"] == "B"


def test_aggregation_pipeline_used_by_reports(db: Database) -> None:
    project_id = ObjectId()
    db.issues.insert_many(
        [
            {"projectId": project_id, "status": "done", "storyPoints": 3},
            {"projectId": project_id, "status": "done", "storyPoints": 5},
            {"projectId": project_id, "status": "todo", "storyPoints": 2},
        ]
    )

    result = list(
        db.issues.aggregate(
            [
                {"$match": {"projectId": project_id}},
                {
                    "$facet": {
                        "byStatus": [
                            {"$group": {"_id": "$status", "points": {"$sum": "$storyPoints"}}},
                            {"$sort": {"_id": 1}},
                        ],
                        "total": [{"$count": "issues"}],
                    }
                },
            ]
        )
    )

    assert result[0]["byStatus"] == [{"_id": "done", "points": 8}, {"_id": "todo", "points": 2}]
    assert result[0]["total"] == [{"issues": 3}]


def test_update_with_aggregation_pipeline(db: Database) -> None:
    db.sprints.insert_one({"_id": "s1", "done": 8, "committed": 10})

    db.sprints.update_one(
        {"_id": "s1"}, [{"$set": {"remaining": {"$subtract": ["$committed", "$done"]}}}]
    )

    assert db.sprints.find_one({"_id": "s1"})["remaining"] == 2
