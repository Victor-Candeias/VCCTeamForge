from concurrent.futures import ThreadPoolExecutor

import pytest
from pymongo.database import Database

from app.domain.permissions import Role


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "dev2": make_user("Dev2", Role.DEVELOPER),
        "qa": make_user("Qa", Role.QA),
        "outsider": make_user("Outsider", Role.DEVELOPER),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


@pytest.fixture
def project(lead_api, people):
    members = [str(people[name].id) for name in ("dev", "dev2", "qa")]
    response = lead_api.post(
        "/api/projects", json={"key": "DVC", "name": "VCCTeamForge", "memberIds": members}
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_issue(api, project, **overrides):
    body = {"projectId": project["id"], "type": "story", "title": "Uma story"} | overrides
    return api.post("/api/issues", json=body)


def test_create_issue_with_sequential_key(lead_api, project, people, indexed_db: Database):
    first = create_issue(
        lead_api,
        project,
        title="  Login  ",
        description="**md**",
        priority="high",
        assigneeId=str(people["dev"].id),
        storyPoints=3.5,
        labels=["Backend", "backend", "api"],
        acceptanceCriteria=["Dado X", " "],
        dueDate="2026-11-01",
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["key"] == "DVC-1"
    assert body["number"] == 1
    assert body["title"] == "Login"
    assert body["status"] == "todo"
    assert body["priority"] == "high"
    assert body["assignee"]["id"] == str(people["dev"].id)
    assert body["reporter"]["id"] == str(people["lead"].id)
    assert body["labels"] == ["backend", "api"]
    assert body["acceptanceCriteria"] == ["Dado X"]
    assert body["dueDate"] == "2026-11-01"
    assert body["canEdit"] is True
    assert body["allowedTransitions"] == ["in_progress"]
    assert body["version"] == 1

    assert create_issue(lead_api, project).json()["key"] == "DVC-2"
    document = indexed_db.issues.find_one({"key": "DVC-1"})
    assert document["priorityRank"] == 3
    assert document["statusRank"] == 1
    assert indexed_db.counters.find_one({"_id": f"issues:{project['id']}"})["value"] == 2


def test_numbering_is_independent_per_project_and_concurrent(lead_api, project):
    other = lead_api.post("/api/projects", json={"key": "OUT", "name": "Outro"}).json()
    assert create_issue(lead_api, other).json()["key"] == "OUT-1"

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: create_issue(lead_api, project), range(16)))
    assert all(response.status_code == 201 for response in responses)
    numbers = sorted(response.json()["number"] for response in responses)
    assert numbers == list(range(1, 17))


def test_get_issue_by_id_and_key(lead_api, project, login_as, people):
    issue = create_issue(lead_api, project).json()

    assert lead_api.get(f"/api/issues/{issue['id']}").json()["key"] == "DVC-1"
    assert lead_api.get("/api/issues/by-key/dvc-1").json()["id"] == issue["id"]
    assert lead_api.get("/api/issues/by-key/DVC-99").status_code == 404
    assert lead_api.get("/api/issues/nao-e-id").status_code == 404

    outsider = login_as(people["outsider"])
    assert outsider.get(f"/api/issues/{issue['id']}").status_code == 404
    assert outsider.get("/api/issues/by-key/DVC-1").status_code == 404
    assert outsider.get(f"/api/issues?projectId={project['id']}").status_code == 404
    assert create_issue(outsider, project).status_code == 404


def test_list_issues_paginated_by_number_desc(lead_api, project):
    for index in range(3):
        create_issue(lead_api, project, title=f"Issue {index}")

    page = lead_api.get(f"/api/issues?projectId={project['id']}&pageSize=2").json()
    assert page["total"] == 3
    assert [item["key"] for item in page["items"]] == ["DVC-3", "DVC-2"]
    assert lead_api.get(f"/api/issues?projectId={project['id']}&sort=-x").status_code == 422


def test_field_validations(lead_api, project, people):
    assert create_issue(lead_api, project, title=" ").status_code == 422
    assert create_issue(lead_api, project, storyPoints=0.3).status_code == 422
    assert create_issue(lead_api, project, labels=["x" * 41]).status_code == 422
    assert create_issue(lead_api, project, type="unknown").status_code == 422
    assert create_issue(lead_api, project, extra=True).status_code == 422
    outsider = create_issue(lead_api, project, assigneeId=str(people["outsider"].id))
    assert outsider.status_code == 422
    assert outsider.json()["field"] == "assigneeId"
    assert create_issue(lead_api, project, assigneeId="nao-e-id").status_code == 422


def test_hierarchy_rules(lead_api, project):
    epic = create_issue(lead_api, project, type="epic", title="Epic").json()
    story = create_issue(lead_api, project, parentIssueId=epic["id"]).json()
    assert story["parent"]["key"] == epic["key"]

    subtask = create_issue(lead_api, project, type="subtask", parentIssueId=story["id"])
    assert subtask.status_code == 201
    assert create_issue(lead_api, project, type="subtask").status_code == 422
    assert (
        create_issue(lead_api, project, type="subtask", parentIssueId=epic["id"]).status_code == 422
    )
    assert create_issue(lead_api, project, parentIssueId=story["id"]).status_code == 422
    assert create_issue(lead_api, project, type="epic", parentIssueId=epic["id"]).status_code == 422

    other = lead_api.post("/api/projects", json={"key": "OUT", "name": "Outro"}).json()
    foreign_epic = create_issue(lead_api, other, type="epic").json()
    assert create_issue(lead_api, project, parentIssueId=foreign_epic["id"]).status_code == 422


def test_dependencies(lead_api, project):
    first = create_issue(lead_api, project).json()
    second = create_issue(lead_api, project, dependsOnIssueIds=[first["id"]]).json()
    assert [dep["key"] for dep in second["dependsOn"]] == ["DVC-1"]

    response = lead_api.patch(
        f"/api/issues/{second['id']}",
        json={"version": second["version"], "dependsOnIssueIds": [second["id"]]},
    )
    assert response.status_code == 422


def test_status_transitions_and_completed_at(lead_api, project):
    issue = create_issue(lead_api, project).json()
    url = f"/api/issues/{issue['id']}"

    invalid = lead_api.patch(url, json={"version": 1, "status": "done"})
    assert invalid.status_code == 422
    assert invalid.json()["field"] == "status"

    issue = lead_api.patch(url, json={"version": 1, "status": "in_progress"}).json()
    issue = lead_api.patch(url, json={"version": issue["version"], "status": "done"}).json()
    assert issue["status"] == "done"
    assert issue["completedAt"] is not None
    assert issue["allowedTransitions"] == ["in_progress"]

    issue = lead_api.patch(url, json={"version": issue["version"], "status": "in_progress"}).json()
    assert issue["completedAt"] is None


def test_block_and_unblock(lead_api, project):
    issue = create_issue(lead_api, project).json()
    url = f"/api/issues/{issue['id']}"

    missing_reason = lead_api.patch(url, json={"version": 1, "blocked": True})
    assert missing_reason.status_code == 422
    assert missing_reason.json()["field"] == "blockReason"

    issue = lead_api.patch(
        url, json={"version": 1, "blocked": True, "blockReason": "À espera da API"}
    ).json()
    assert issue["blocked"] is True
    assert issue["blockReason"] == "À espera da API"
    assert issue["blockedAt"] is not None

    issue = lead_api.patch(url, json={"version": issue["version"], "blocked": False}).json()
    assert issue["blocked"] is False
    assert issue["blockReason"] is None
    assert issue["blockedAt"] is None


def test_edit_rules_by_role(lead_api, project, login_as, people):
    dev_api = login_as(people["dev"])
    others = create_issue(lead_api, project, assigneeId=str(people["dev2"].id)).json()
    assigned = create_issue(lead_api, project, assigneeId=str(people["dev"].id)).json()

    forbidden = dev_api.patch(f"/api/issues/{others['id']}", json={"version": 1, "title": "x"})
    assert forbidden.status_code == 403
    assert dev_api.get(f"/api/issues/{others['id']}").json()["canEdit"] is False

    allowed = dev_api.patch(f"/api/issues/{assigned['id']}", json={"version": 1, "title": "Novo"})
    assert allowed.status_code == 200
    assert allowed.json()["title"] == "Novo"

    reported = create_issue(dev_api, project, title="Minha").json()
    edited = dev_api.patch(f"/api/issues/{reported['id']}", json={"version": 1, "priority": "low"})
    assert edited.status_code == 200

    admin_api = login_as(people["admin"])
    assert (
        admin_api.patch(
            f"/api/issues/{others['id']}", json={"version": 1, "title": "A"}
        ).status_code
        == 200
    )


def test_qa_creates_only_bugs(project, login_as, people):
    qa_api = login_as(people["qa"])
    assert create_issue(qa_api, project, type="story").status_code == 403
    assert create_issue(qa_api, project, type="bug", title="Erro").status_code == 201


def test_archived_project_is_read_only(lead_api, project):
    issue = create_issue(lead_api, project).json()
    archived = lead_api.post(
        f"/api/projects/{project['id']}/archive", json={"version": project["version"]}
    )
    assert archived.status_code == 200

    assert create_issue(lead_api, project).status_code == 422
    response = lead_api.patch(f"/api/issues/{issue['id']}", json={"version": 1, "title": "x"})
    assert response.status_code == 422
    detail = lead_api.get(f"/api/issues/{issue['id']}").json()
    assert detail["canEdit"] is False
    assert detail["allowedTransitions"] == []


def test_version_conflict(lead_api, project):
    issue = create_issue(lead_api, project).json()
    url = f"/api/issues/{issue['id']}"
    assert lead_api.patch(url, json={"version": 1, "title": "Primeira"}).status_code == 200

    stale = lead_api.patch(url, json={"version": 1, "title": "Segunda"})
    assert stale.status_code == 409
    assert stale.json()["currentVersion"] == 2

    unchanged = lead_api.patch(url, json={"version": 2, "title": "Primeira"})
    assert unchanged.status_code == 200
    assert unchanged.json()["version"] == 2


def test_type_is_not_editable_and_requires_csrf(lead_api, project):
    issue = create_issue(lead_api, project).json()
    url = f"/api/issues/{issue['id']}"
    assert lead_api.patch(url, json={"version": 1, "type": "bug"}).status_code == 422

    response = lead_api.client.patch(url, json={"version": 1, "title": "x"})
    assert response.status_code == 403
