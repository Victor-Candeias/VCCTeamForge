from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo.database import Database

from app.core.config import DEFAULT_DATABASE_DIR
from app.domain.permissions import Role
from app.maintenance import migrations
from app.services import issues as issue_service


@pytest.fixture
def people(make_user):
    return {
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "outsider": make_user("Outsider", Role.DEVELOPER),
    }


@pytest.fixture
def apis(login_as, people):
    return {name: login_as(user) for name, user in people.items()}


def _project(api, key, members=()):
    response = api.post(
        "/api/projects", json={"key": key, "name": f"Projeto {key}", "memberIds": list(members)}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def project(apis, people):
    return _project(apis["lead"], "BRD", [str(people["dev"].id)])


def _create(api, project, title, **extra):
    response = api.post(
        "/api/issues",
        json={"projectId": project["id"], "type": "task", "title": title, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _order(api, project):
    response = api.get(
        "/api/issues", params={"projectId": project["id"], "sort": "rank", "pageSize": 100}
    )
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["items"]]


def _move(api, issue, **body):
    current = api.get(f"/api/issues/{issue['id']}").json()
    return api.post(f"/api/issues/{issue['id']}/rank", json={"version": current["version"], **body})


@pytest.fixture
def three(apis, project):
    return [_create(apis["lead"], project, title) for title in ("A", "B", "C")]


def test_new_issues_get_increasing_rank(apis, project, three):
    ranks = [apis["lead"].get(f"/api/issues/{i['id']}").json()["rank"] for i in three]
    assert ranks == [1024.0, 2048.0, 3072.0]
    assert _order(apis["lead"], project) == ["A", "B", "C"]


def test_move_between_neighbours_top_and_bottom(apis, project, three):
    a, b, c = three
    response = _move(apis["lead"], c, beforeId=b["id"])
    assert response.status_code == 200, response.text
    assert response.json()["rank"] == pytest.approx(1536.0)
    assert _order(apis["lead"], project) == ["A", "C", "B"]

    assert _move(apis["lead"], b, beforeId=a["id"]).status_code == 200
    assert _order(apis["lead"], project) == ["B", "A", "C"]

    assert _move(apis["lead"], b, afterId=c["id"]).status_code == 200
    assert _order(apis["lead"], project) == ["A", "C", "B"]

    assert _move(apis["lead"], a, afterId=c["id"], beforeId=b["id"]).status_code == 200
    assert _order(apis["lead"], project) == ["C", "A", "B"]


def test_move_rejects_inconsistent_neighbours(apis, project, three):
    a, b, c = three
    response = _move(apis["lead"], b, afterId=c["id"], beforeId=a["id"])
    assert response.status_code == 422
    assert response.json()["field"] == "beforeId"

    response = _move(apis["lead"], b, beforeId=b["id"])
    assert response.status_code == 422

    response = apis["lead"].post(f"/api/issues/{b['id']}/rank", json={"version": 1})
    assert response.status_code == 422


def test_move_rejects_neighbour_from_other_project(apis, project, three):
    other = _project(apis["lead"], "OTH")
    foreign = _create(apis["lead"], other, "Fora")
    response = _move(apis["lead"], three[0], beforeId=foreign["id"])
    assert response.status_code == 422
    assert response.json()["field"] == "beforeId"

    response = _move(apis["lead"], three[0], afterId=str(ObjectId()))
    assert response.status_code == 422
    assert response.json()["field"] == "afterId"


def test_move_renormalizes_when_gap_is_exhausted(apis, project, three, indexed_db: Database):
    a, b, c = three
    indexed_db.issues.update_one({"_id": ObjectId(b["id"])}, {"$set": {"rank": 1024.0}})
    response = _move(apis["lead"], c, afterId=a["id"], beforeId=b["id"])
    assert response.status_code == 200, response.text
    assert _order(apis["lead"], project) == ["A", "C", "B"]
    ranks = sorted(doc["rank"] for doc in indexed_db.issues.find())
    assert ranks[0] == 1024.0 and ranks[-1] == 2048.0


def test_move_checks_version_and_permissions(apis, people, project, three):
    a, b, _ = three
    response = apis["lead"].post(
        f"/api/issues/{a['id']}/rank", json={"version": 99, "beforeId": b["id"]}
    )
    assert response.status_code == 409

    assert _move(apis["dev"], b, beforeId=a["id"]).status_code == 403
    assigned = _create(apis["lead"], project, "Minha", assigneeId=str(people["dev"].id))
    assert _move(apis["dev"], assigned, beforeId=a["id"]).status_code == 200
    assert _order(apis["lead"], project)[0] == "Minha"

    response = apis["outsider"].post(
        f"/api/issues/{a['id']}/rank", json={"version": 1, "beforeId": b["id"]}
    )
    assert response.status_code == 404


def test_rank_change_does_not_write_history(apis, three, indexed_db: Database):
    before = indexed_db.issue_history.count_documents({})
    assert _move(apis["lead"], three[2], beforeId=three[0]["id"]).status_code == 200
    assert indexed_db.issue_history.count_documents({}) == before


def _set_status(api, issue, status):
    current = api.get(f"/api/issues/{issue['id']}").json()
    return api.patch(
        f"/api/issues/{issue['id']}", json={"status": status, "version": current["version"]}
    )


def test_board_groups_by_status_in_rank_order(apis, project, three, indexed_db: Database):
    a, b, c = three
    assert _set_status(apis["lead"], b, "in_progress").status_code == 200
    assert _set_status(apis["lead"], c, "in_progress").status_code == 200
    assert _move(apis["lead"], c, beforeId=b["id"]).status_code == 200
    old = _create(apis["lead"], project, "Antiga")
    assert _set_status(apis["lead"], old, "in_progress").status_code == 200
    assert _set_status(apis["lead"], old, "done").status_code == 200
    recent = _create(apis["lead"], project, "Recente")
    assert _set_status(apis["lead"], recent, "in_progress").status_code == 200
    assert _set_status(apis["lead"], recent, "done").status_code == 200
    indexed_db.issues.update_one(
        {"_id": ObjectId(old["id"])},
        {"$set": {"completedAt": datetime.now(UTC) - timedelta(days=15)}},
    )

    response = apis["dev"].get(f"/api/projects/{project['id']}/board")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    board = response.json()
    assert board["columnLimit"] == 200 and board["doneWindowDays"] == 14
    columns = {col["status"]: col for col in board["columns"]}
    assert list(columns) == ["todo", "in_progress", "code_review", "testing", "done"]
    assert [i["title"] for i in columns["todo"]["items"]] == ["A"]
    assert [i["title"] for i in columns["in_progress"]["items"]] == ["C", "B"]
    assert [i["title"] for i in columns["done"]["items"]] == ["Recente"]
    assert columns["done"]["total"] == 1 and columns["done"]["truncated"] is False

    filtered = (
        apis["dev"]
        .get(f"/api/projects/{project['id']}/board", params={"q": "B", "status": "todo"})
        .json()
    )
    titles = [i["title"] for col in filtered["columns"] for i in col["items"]]
    assert titles == ["B"]

    assert apis["outsider"].get(f"/api/projects/{project['id']}/board").status_code == 404


def test_board_truncates_columns(apis, project, monkeypatch):
    monkeypatch.setattr(issue_service, "BOARD_COLUMN_LIMIT", 2)
    for title in ("A", "B", "C"):
        _create(apis["lead"], project, title)
    board = apis["lead"].get(f"/api/projects/{project['id']}/board").json()
    todo = board["columns"][0]
    assert [i["title"] for i in todo["items"]] == ["A", "B"]
    assert todo["total"] == 3 and todo["truncated"] is True and board["columnLimit"] == 2


def test_board_move_with_invalid_transition_is_rejected(apis, three):
    response = _set_status(apis["lead"], three[0], "done")
    assert response.status_code == 422


def test_rank_migration_fills_missing_ranks(db: Database):
    project_id = ObjectId()
    db.issues.insert_many(
        [
            {"projectId": project_id, "number": 2, "rank": None},
            {"projectId": project_id, "number": 1},
            {"projectId": project_id, "number": 3, "rank": 5000.0},
        ]
    )
    migration = next(
        m for m in migrations.discover_migrations(DEFAULT_DATABASE_DIR) if m.id == "0003_issue_rank"
    )
    migration.up(db)
    migration.up(db)
    ranks = {doc["number"]: doc["rank"] for doc in db.issues.find()}
    assert ranks == {1: 6024.0, 2: 7048.0, 3: 5000.0}
