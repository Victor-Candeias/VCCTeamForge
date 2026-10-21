import pytest
from bson import ObjectId
from pymongo.database import Database

from app.domain.permissions import Role


@pytest.fixture
def people(make_user):
    return {
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "outsider": make_user("Outsider", Role.TECH_LEAD),
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


def _sprint(api, project, name="Sprint 1", start="2026-11-02", end="2026-11-13", **extra):
    body = {"projectId": project["id"], "name": name, "startDate": start, "endDate": end}
    response = api.post("/api/sprints", json=body | extra)
    assert response.status_code == 201, response.text
    return response.json()


def _issue(api, project, title="Story", **fields):
    body = {"projectId": project["id"], "type": "story", "title": title} | fields
    response = api.post("/api/issues", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _add(api, sprint, *issues):
    return api.post(
        f"/api/sprints/{sprint['id']}/issues", json={"issueIds": [i["id"] for i in issues]}
    )


def test_add_issues_updates_scope_and_history(lead_api, project, indexed_db: Database):
    sprint = _sprint(lead_api, project, capacityStoryPoints=20)
    first = _issue(lead_api, project, "A", storyPoints=5)
    second = _issue(lead_api, project, "B", storyPoints=3.5)
    third = _issue(lead_api, project, "C")

    response = _add(lead_api, sprint, first, second, third)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["capacityStoryPoints"] == 20
    assert body["scope"] == {
        "issueCount": 3,
        "storyPoints": 8.5,
        "unestimatedCount": 1,
        "completedIssueCount": 0,
        "completedStoryPoints": 0,
    }
    issue = indexed_db.issues.find_one({"_id": ObjectId(first["id"])})
    assert issue["sprintId"] == ObjectId(sprint["id"])
    assert issue["version"] == first["version"] + 1
    history = indexed_db.issue_history.find_one(
        {"issueId": issue["_id"], "changes.field": "sprintId"}
    )
    assert history["changes"] == [{"field": "sprintId", "from": None, "to": sprint["id"]}]
    audit = indexed_db.audit_logs.find_one({"action": "sprint.issues_added"})
    assert audit["details"]["issueKeys"] == ["DVC-1", "DVC-2", "DVC-3"]

    found = lead_api.get(
        "/api/issues", params={"projectId": project["id"], "sprintId": sprint["id"]}
    ).json()
    assert found["total"] == 3


def test_adding_twice_is_idempotent(lead_api, project, indexed_db: Database):
    sprint = _sprint(lead_api, project)
    issue = _issue(lead_api, project)
    assert _add(lead_api, sprint, issue).status_code == 200

    response = _add(lead_api, sprint, issue)

    assert response.status_code == 200
    assert response.json()["scope"]["issueCount"] == 1
    assert indexed_db.issues.find_one({"_id": ObjectId(issue["id"])})["version"] == 2


def test_move_issue_between_open_sprints(lead_api, project):
    first = _sprint(lead_api, project)
    second = _sprint(lead_api, project, "Sprint 2", "2026-11-16", "2026-11-27")
    issue = _issue(lead_api, project, storyPoints=2)
    _add(lead_api, first, issue)

    response = _add(lead_api, second, issue)

    assert response.status_code == 200
    assert response.json()["scope"]["storyPoints"] == 2
    assert lead_api.get(f"/api/sprints/{first['id']}").json()["scope"]["issueCount"] == 0


@pytest.mark.parametrize(
    ("fields", "status"),
    [({"type": "epic"}, "todo"), ({}, "done")],
)
def test_epics_and_done_issues_are_not_plannable(lead_api, project, fields, status):
    sprint = _sprint(lead_api, project)
    issue = _issue(lead_api, project, **fields)
    if status == "done":
        url = f"/api/issues/{issue['id']}"
        for target in ("in_progress", "code_review", "testing", "done"):
            issue = lead_api.patch(url, json={"version": issue["version"], "status": target}).json()

    response = _add(lead_api, sprint, issue)

    assert response.status_code == 422
    assert response.json()["field"] == "issueIds"
    assert response.json()["issueId"] == issue["id"]


def test_issue_from_other_project_is_rejected(lead_api, project, people):
    other = lead_api.post("/api/projects", json={"key": "OTH", "name": "Outro"}).json()
    sprint = _sprint(lead_api, project)
    foreign = _issue(lead_api, other)

    response = _add(lead_api, sprint, foreign)

    assert response.status_code == 422
    assert response.json()["field"] == "issueIds"


def test_closed_sprints_are_frozen(lead_api, project, indexed_db: Database):
    sprint = _sprint(lead_api, project)
    issue = _issue(lead_api, project)
    _add(lead_api, sprint, issue)
    indexed_db.sprints.update_one({"_id": ObjectId(sprint["id"])}, {"$set": {"status": "closed"}})
    other = _sprint(lead_api, project, "Sprint 2", "2026-11-16", "2026-11-27")

    assert _add(lead_api, sprint, _issue(lead_api, project)).status_code == 422
    assert _add(lead_api, other, issue).status_code == 422
    removed = lead_api.delete(f"/api/sprints/{sprint['id']}/issues/{issue['id']}")
    assert removed.status_code == 422


def test_remove_issue_returns_it_to_backlog(lead_api, project, indexed_db: Database):
    sprint = _sprint(lead_api, project)
    issue = _issue(lead_api, project, storyPoints=3)
    _add(lead_api, sprint, issue)

    response = lead_api.delete(f"/api/sprints/{sprint['id']}/issues/{issue['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["scope"]["issueCount"] == 0
    assert indexed_db.issues.find_one({"_id": ObjectId(issue["id"])})["sprintId"] is None
    assert indexed_db.audit_logs.count_documents({"action": "sprint.issue_removed"}) == 1
    again = lead_api.delete(f"/api/sprints/{sprint['id']}/issues/{issue['id']}")
    assert again.status_code == 404


def test_planning_requires_sprint_management(login_as, people, lead_api, project):
    sprint = _sprint(lead_api, project)
    issue = _issue(lead_api, project)

    assert _add(login_as(people["dev"]), sprint, issue).status_code == 403
    assert _add(login_as(people["outsider"]), sprint, issue).status_code == 404


def test_sprint_issue_limit(lead_api, project, indexed_db: Database, monkeypatch):
    monkeypatch.setattr("app.services.sprint_planning.SPRINT_ISSUES_MAX", 1)
    sprint = _sprint(lead_api, project)
    _add(lead_api, sprint, _issue(lead_api, project, "A"))

    response = _add(lead_api, sprint, _issue(lead_api, project, "B"))

    assert response.status_code == 422
    assert "máximo" in response.json()["detail"]


@pytest.mark.parametrize("capacity", [-1, 1001, 2.3])
def test_invalid_capacity(lead_api, project, capacity):
    body = {
        "projectId": project["id"],
        "name": "S",
        "startDate": "2026-11-02",
        "endDate": "2026-11-13",
        "capacityStoryPoints": capacity,
    }
    response = lead_api.post("/api/sprints", json=body)

    assert response.status_code == 422


def test_update_capacity(lead_api, project, indexed_db: Database):
    sprint = _sprint(lead_api, project)
    url = f"/api/sprints/{sprint['id']}"

    updated = lead_api.patch(url, json={"version": 1, "capacityStoryPoints": 13.5}).json()
    assert updated["capacityStoryPoints"] == 13.5
    cleared = lead_api.patch(url, json={"version": 2, "capacityStoryPoints": None}).json()
    assert cleared["capacityStoryPoints"] is None
