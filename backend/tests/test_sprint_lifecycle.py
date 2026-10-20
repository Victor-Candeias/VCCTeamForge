from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from app.domain.permissions import Role

TODAY = datetime.now(UTC).date()


def _day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


@pytest.fixture
def people(make_user):
    return {
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


@pytest.fixture
def project(lead_api, people):
    response = lead_api.post(
        "/api/projects",
        json={"key": "DVC", "name": "VCCTeamForge", "memberIds": [str(people["dev"].id)]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sprint(api, project, name="Sprint 1", start=0, end=9):
    body = {
        "projectId": project["id"],
        "name": name,
        "startDate": _day(start),
        "endDate": _day(end),
    }
    response = api.post("/api/sprints", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _issue(api, project, title="Story", **fields):
    body = {"projectId": project["id"], "type": "story", "title": title} | fields
    response = api.post("/api/issues", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _add(api, sprint, *issues):
    response = api.post(
        f"/api/sprints/{sprint['id']}/issues", json={"issueIds": [i["id"] for i in issues]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _start(api, sprint, version=None):
    current = api.get(f"/api/sprints/{sprint['id']}").json()
    return api.post(
        f"/api/sprints/{sprint['id']}/start", json={"version": version or current["version"]}
    )


@pytest.fixture
def planned(lead_api, project):
    sprint = _sprint(lead_api, project)
    issues = [
        _issue(lead_api, project, "A", storyPoints=5),
        _issue(lead_api, project, "B", storyPoints=3),
        _issue(lead_api, project, "C"),
    ]
    _add(lead_api, sprint, *issues)
    return sprint, issues


def test_start_freezes_commitment(lead_api, planned, people, indexed_db: Database):
    sprint, issues = planned

    response = _start(lead_api, sprint)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["committedIssueCount"] == 3
    assert body["committedStoryPoints"] == 8
    assert body["startedAt"] is not None
    assert body["version"] == 2
    document = indexed_db.sprints.find_one({"_id": ObjectId(sprint["id"])})
    assert document["startedBy"] == people["lead"].id
    snapshot = indexed_db.sprint_snapshots.find_one({"sprintId": document["_id"]})
    assert snapshot["kind"] == "commitment"
    assert snapshot["day"] == TODAY.isoformat()
    assert [item["key"] for item in snapshot["issues"]] == ["DVC-1", "DVC-2", "DVC-3"]
    assert snapshot["totals"]["storyPoints"] == 8
    assert snapshot["totals"]["unestimatedCount"] == 1
    audit = indexed_db.audit_logs.find_one({"action": "sprint.started"})
    assert audit["details"]["committedStoryPoints"] == 8


def test_commitment_tracks_scope_changes(lead_api, project, planned):
    sprint, issues = planned
    assert _start(lead_api, sprint).status_code == 200
    late = _issue(lead_api, project, "D", storyPoints=2)
    _add(lead_api, sprint, late)
    lead_api.delete(f"/api/sprints/{sprint['id']}/issues/{issues[1]['id']}")
    url = f"/api/issues/{issues[0]['id']}"
    lead_api.patch(url, json={"version": issues[0]["version"] + 1, "storyPoints": 8})

    response = lead_api.get(f"/api/sprints/{sprint['id']}/commitment")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["issueCount"] == 3
    assert body["storyPoints"] == 8
    assert body["removedCount"] == 1
    assert body["addedCount"] == 1
    assert body["addedStoryPoints"] == 2
    first, second, _ = body["issues"]
    assert first["storyPoints"] == 5
    assert first["currentStoryPoints"] == 8
    assert first["inSprint"] is True
    assert second["inSprint"] is False
    assert body["added"][0]["key"] == "DVC-4"


def test_commitment_requires_started_sprint(lead_api, planned):
    sprint, _ = planned

    assert lead_api.get(f"/api/sprints/{sprint['id']}/commitment").status_code == 404


def test_only_planned_sprints_start(lead_api, planned):
    sprint, _ = planned
    assert _start(lead_api, sprint).status_code == 200

    response = _start(lead_api, sprint)

    assert response.status_code == 422
    assert response.json()["field"] == "status"


def test_one_active_sprint_per_project(lead_api, project, planned):
    sprint, _ = planned
    _start(lead_api, sprint)
    other = _sprint(lead_api, project, "Sprint 2", 10, 19)
    _add(lead_api, other, _issue(lead_api, project, "E"))

    response = _start(lead_api, other)

    assert response.status_code == 422
    assert response.json()["field"] == "status"
    assert response.json()["sprintId"] == sprint["id"]


def test_active_index_guards_concurrent_starts(lead_api, project, planned, monkeypatch):
    sprint, _ = planned
    _start(lead_api, sprint)
    other = _sprint(lead_api, project, "Sprint 2", 10, 19)
    _add(lead_api, other, _issue(lead_api, project, "E"))
    monkeypatch.setattr(
        "app.repositories.sprints.SprintRepository.find_active", lambda self, project_id: None
    )

    response = _start(lead_api, other)

    assert response.status_code == 422
    assert response.json()["field"] == "status"


def test_empty_or_expired_sprints_do_not_start(lead_api, project, indexed_db: Database):
    empty = _sprint(lead_api, project)
    response = _start(lead_api, empty)
    assert response.status_code == 422
    assert response.json()["field"] == "issueIds"

    expired = _sprint(lead_api, project, "Sprint 0", -20, -11)
    _add(lead_api, expired, _issue(lead_api, project))
    response = _start(lead_api, expired)
    assert response.status_code == 422
    assert response.json()["field"] == "endDate"


def test_start_checks_version_and_permission(lead_api, login_as, people, planned):
    sprint, _ = planned

    conflict = _start(lead_api, sprint, version=5)
    assert conflict.status_code == 409
    assert conflict.json()["currentVersion"] == 1
    assert _start(login_as(people["dev"]), sprint).status_code == 403


def test_failed_snapshot_reverts_start(lead_api, planned, indexed_db: Database, monkeypatch):
    sprint, _ = planned

    def fail(self, document):
        raise ConnectionFailure("falha simulada")

    monkeypatch.setattr("app.repositories.sprint_snapshots.SprintSnapshotRepository.save", fail)

    response = _start(lead_api, sprint)

    assert response.status_code == 503
    document = indexed_db.sprints.find_one({"_id": ObjectId(sprint["id"])})
    assert document["status"] == "planned"
    assert document["startedAt"] is None
    assert document["committedStoryPoints"] is None


def test_sprint_board_shows_all_done_issues(lead_api, project, planned, indexed_db: Database):
    sprint, issues = planned
    old = datetime.now(UTC) - timedelta(days=30)
    indexed_db.issues.update_one(
        {"_id": ObjectId(issues[0]["id"])}, {"$set": {"status": "done", "completedAt": old}}
    )
    url = f"/api/projects/{project['id']}/board"

    sprint_board = lead_api.get(url, params={"sprintId": sprint["id"]}).json()
    full_board = lead_api.get(url).json()

    assert sprint_board["doneWindowDays"] is None
    assert [column["total"] for column in sprint_board["columns"]] == [2, 0, 0, 0, 1]
    assert full_board["doneWindowDays"] == 14
    assert full_board["columns"][-1]["total"] == 0
