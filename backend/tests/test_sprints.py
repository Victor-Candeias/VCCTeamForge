import pytest
from bson import ObjectId
from pymongo.database import Database

from app.domain.permissions import Role


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "qa": make_user("Qa", Role.QA),
        "outsider": make_user("Outsider", Role.TECH_LEAD),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


@pytest.fixture
def project(lead_api, people):
    response = lead_api.post(
        "/api/projects",
        json={
            "key": "DVC",
            "name": "VCCTeamForge",
            "memberIds": [str(people["dev"].id), str(people["qa"].id)],
            "settings": {"sprintDurationDays": 10},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create(api, project, **overrides):
    body = {
        "projectId": project["id"],
        "name": "Sprint 1",
        "goal": "Concluir autenticação",
        "startDate": "2026-11-02",
        "endDate": "2026-11-13",
    } | overrides
    return api.post("/api/sprints", json=body)


def test_create_sprint(lead_api, project, people, indexed_db: Database):
    response = _create(lead_api, project, name="  Sprint   1 ", goal=" Objetivo ")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Sprint 1"
    assert body["goal"] == "Objetivo"
    assert body["status"] == "planned"
    assert body["startDate"] == "2026-11-02"
    assert body["endDate"] == "2026-11-13"
    assert body["durationDays"] == 12
    assert body["committedStoryPoints"] is None
    assert body["committedIssueCount"] is None
    assert body["version"] == 1
    assert body["canEdit"] is True

    document = indexed_db.sprints.find_one({"_id": ObjectId(body["id"])})
    assert document["projectId"] == ObjectId(project["id"])
    assert document["nameKey"] == "sprint 1"
    assert document["createdBy"] == people["lead"].id
    audit = indexed_db.audit_logs.find_one({"action": "sprint.created"})
    assert audit["entityId"] == document["_id"]
    assert audit["details"]["projectKey"] == "DVC"


def test_end_date_defaults_to_project_sprint_duration(lead_api, project):
    response = _create(lead_api, project, endDate=None)

    assert response.status_code == 201, response.text
    assert response.json()["endDate"] == "2026-11-11"
    assert response.json()["durationDays"] == 10


def test_create_validations(lead_api, project):
    assert _create(lead_api, project).status_code == 201

    duplicated = _create(lead_api, project, name="sprint 1", startDate="2026-12-01", endDate=None)
    assert duplicated.status_code == 409
    assert duplicated.json()["field"] == "name"

    reversed_dates = _create(
        lead_api, project, name="S2", startDate="2026-12-10", endDate="2026-12-01"
    )
    assert reversed_dates.status_code == 422
    assert reversed_dates.json()["field"] == "endDate"

    too_long = _create(lead_api, project, name="S3", startDate="2027-01-01", endDate="2027-03-15")
    assert too_long.status_code == 422
    assert too_long.json()["field"] == "endDate"

    overlapping = _create(lead_api, project, name="S4", startDate="2026-11-13", endDate=None)
    assert overlapping.status_code == 422
    assert overlapping.json()["field"] == "startDate"
    assert "Sprint 1" in overlapping.json()["detail"]

    assert _create(lead_api, project, name="   ").status_code == 422
    assert _create(lead_api, project, name="S5", projectId="nao-e-id").status_code == 422
    assert _create(lead_api, project, name="S6", projectId=str(ObjectId())).status_code == 422
    assert _create(lead_api, project, name="S7", extra=1).status_code == 422
    assert _create(lead_api, project, name="S8", startDate=None).status_code == 422

    adjacent = _create(lead_api, project, name="Sprint 2", startDate="2026-11-14", endDate=None)
    assert adjacent.status_code == 201, adjacent.text


def test_permissions(login_as, people, project):
    assert _create(login_as(people["dev"]), project).status_code == 403
    assert _create(login_as(people["qa"]), project).status_code == 403
    outsider = _create(login_as(people["outsider"]), project)
    assert outsider.status_code == 422
    assert outsider.json()["field"] == "projectId"
    assert _create(login_as(people["admin"]), project).status_code == 201


def test_read_requires_project_access(login_as, lead_api, people, project):
    sprint = _create(lead_api, project).json()

    dev = login_as(people["dev"])
    listed = dev.get("/api/sprints", params={"projectId": project["id"]})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [sprint["id"]]
    detail = dev.get(f"/api/sprints/{sprint['id']}").json()
    assert detail["canEdit"] is False

    outsider = login_as(people["outsider"])
    assert outsider.get("/api/sprints", params={"projectId": project["id"]}).status_code == 404
    assert outsider.get(f"/api/sprints/{sprint['id']}").status_code == 404
    assert lead_api.get("/api/sprints/nao-e-id").status_code == 404
    assert lead_api.get("/api/sprints", params={"projectId": "x"}).status_code == 404
    assert lead_api.get("/api/sprints").status_code == 422


def test_list_filters_sort_and_pagination(lead_api, project, indexed_db: Database):
    for index, start in enumerate(["2026-11-02", "2026-11-16", "2026-11-30"], start=1):
        _create(lead_api, project, name=f"Sprint {index}", startDate=start, endDate=None)
    indexed_db.sprints.update_one({"name": "Sprint 1"}, {"$set": {"status": "closed"}})

    default = lead_api.get("/api/sprints", params={"projectId": project["id"]}).json()
    assert [item["name"] for item in default["items"]] == ["Sprint 3", "Sprint 2", "Sprint 1"]
    assert default["total"] == 3

    planned = lead_api.get(
        "/api/sprints",
        params={"projectId": project["id"], "status": "planned", "sort": "startDate"},
    ).json()
    assert [item["name"] for item in planned["items"]] == ["Sprint 2", "Sprint 3"]

    page = lead_api.get(
        "/api/sprints",
        params={"projectId": project["id"], "sort": "name", "pageSize": 1, "page": 2},
    ).json()
    assert [item["name"] for item in page["items"]] == ["Sprint 2"]

    invalid = lead_api.get("/api/sprints", params={"projectId": project["id"], "sort": "goal"})
    assert invalid.status_code == 422


def test_update_planned_sprint(lead_api, project, indexed_db: Database):
    sprint = _create(lead_api, project).json()

    response = lead_api.patch(
        f"/api/sprints/{sprint['id']}",
        json={
            "version": 1,
            "name": "Sprint inicial",
            "goal": "Novo objetivo",
            "startDate": "2026-11-03",
            "endDate": "2026-11-16",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Sprint inicial"
    assert body["goal"] == "Novo objetivo"
    assert body["startDate"] == "2026-11-03"
    assert body["endDate"] == "2026-11-16"
    assert body["version"] == 2
    audit = indexed_db.audit_logs.find_one({"action": "sprint.updated"})
    assert set(audit["details"]["changes"]) == {"name", "goal", "startDate", "endDate"}

    unchanged = lead_api.patch(
        f"/api/sprints/{sprint['id']}", json={"version": 2, "goal": "Novo objetivo"}
    )
    assert unchanged.json()["version"] == 2


def test_update_validations_and_conflicts(lead_api, project):
    first = _create(lead_api, project).json()
    _create(lead_api, project, name="Sprint 2", startDate="2026-11-16", endDate=None)
    path = f"/api/sprints/{first['id']}"

    stale = lead_api.patch(path, json={"version": 9, "goal": "x"})
    assert stale.status_code == 409
    assert stale.json()["currentVersion"] == 1

    duplicated = lead_api.patch(path, json={"version": 1, "name": "SPRINT 2"})
    assert duplicated.status_code == 409
    assert duplicated.json()["field"] == "name"

    overlap = lead_api.patch(path, json={"version": 1, "endDate": "2026-11-20"})
    assert overlap.status_code == 422
    assert overlap.json()["field"] == "startDate"

    reversed_dates = lead_api.patch(path, json={"version": 1, "startDate": "2026-11-14"})
    assert reversed_dates.status_code == 422
    assert reversed_dates.json()["field"] == "endDate"

    assert lead_api.patch(path, json={"version": 1, "endDate": None}).status_code == 422
    assert lead_api.patch(path, json={"version": 1, "status": "active"}).status_code == 422
    assert lead_api.patch(f"/api/sprints/{ObjectId()}", json={"version": 1}).status_code == 404


def test_active_and_closed_sprints(lead_api, project, indexed_db: Database):
    sprint = _create(lead_api, project).json()
    path = f"/api/sprints/{sprint['id']}"
    indexed_db.sprints.update_one({"_id": ObjectId(sprint["id"])}, {"$set": {"status": "active"}})

    moved = lead_api.patch(path, json={"version": 1, "startDate": "2026-11-03"})
    assert moved.status_code == 422
    assert moved.json()["field"] == "startDate"
    extended = lead_api.patch(path, json={"version": 1, "endDate": "2026-11-15", "name": "S1"})
    assert extended.status_code == 200, extended.text
    assert extended.json()["endDate"] == "2026-11-15"

    indexed_db.sprints.update_one({"_id": ObjectId(sprint["id"])}, {"$set": {"status": "closed"}})
    assert lead_api.get(path).json()["canEdit"] is False
    assert lead_api.patch(path, json={"version": 2, "goal": "x"}).status_code == 422

    # Sprints fechados não bloqueiam o calendário.
    reused = _create(lead_api, project, name="Sprint 2", startDate="2026-11-05", endDate=None)
    assert reused.status_code == 201, reused.text


def test_archived_project_is_read_only(login_as, lead_api, people, project):
    sprint = _create(lead_api, project).json()
    lead_api.post(f"/api/projects/{project['id']}/archive", json={"version": project["version"]})

    assert _create(lead_api, project, name="S2", startDate="2027-01-04").status_code == 422
    assert (
        lead_api.patch(f"/api/sprints/{sprint['id']}", json={"version": 1, "goal": "x"}).status_code
        == 422
    )
    assert lead_api.get(f"/api/sprints/{sprint['id']}").json()["canEdit"] is False
    assert login_as(people["dev"]).get(f"/api/sprints/{sprint['id']}").status_code == 200
