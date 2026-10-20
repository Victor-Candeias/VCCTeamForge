import pytest
from bson import ObjectId
from pymongo.database import Database

from app.domain.permissions import Role


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lead", Role.TECH_LEAD),
        "lead2": make_user("Lead2", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "qa": make_user("Qa", Role.QA),
        "inactive": make_user("Inactive", Role.DEVELOPER, active=False),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


def _create(api, **overrides):
    body = {"key": "dvc", "name": "VCCTeamForge", "description": "Gestão técnica"} | overrides
    return api.post("/api/projects", json=body)


def test_create_project_normalizes_key_and_sets_lead(lead_api, people, indexed_db: Database):
    response = _create(lead_api, startDate="2026-10-01", targetDate="2026-12-31")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["key"] == "DVC"
    assert body["status"] == "active"
    assert body["priority"] == "medium"
    assert body["lead"]["id"] == str(people["lead"].id)
    assert body["memberCount"] == 1
    assert body["startDate"] == "2026-10-01"
    assert body["settings"] == {
        "methodology": "scrum",
        "sprintDurationDays": 14,
        "estimationType": "story_points",
    }
    assert body["version"] == 1
    assert body["canManage"] is True

    document = indexed_db.projects.find_one({"key": "DVC"})
    assert document["leadUserId"] == people["lead"].id
    assert document["memberIds"] == [people["lead"].id]
    audit = indexed_db.audit_logs.find_one({"action": "project.created"})
    assert audit["actorId"] == people["lead"].id
    assert audit["entityId"] == document["_id"]


def test_create_project_validations(lead_api, people):
    assert _create(lead_api).status_code == 201
    duplicated = _create(lead_api, name="Outro")
    assert duplicated.status_code == 409
    assert duplicated.json()["field"] == "key"

    assert _create(lead_api, key="1AB").status_code == 422
    assert _create(lead_api, key="AB", name="   ").status_code == 422
    assert (
        _create(lead_api, key="AC", startDate="2026-10-02", targetDate="2026-10-01").status_code
        == 422
    )
    assert _create(lead_api, key="AD", leadUserId=str(people["dev"].id)).status_code == 422
    assert _create(lead_api, key="AE", memberIds=[str(people["inactive"].id)]).status_code == 422
    assert _create(lead_api, key="AF", memberIds=["nao-e-id"]).status_code == 422
    assert _create(lead_api, key="AG", status="archived").status_code == 422
    assert _create(lead_api, key="AH", memberIds=[], extra=1).status_code == 422


def test_only_project_managers_can_create(login_as, people):
    assert _create(login_as(people["dev"])).status_code == 403
    assert _create(login_as(people["qa"])).status_code == 403
    admin_project = _create(login_as(people["admin"])).json()
    assert admin_project["lead"] is None


def test_create_requires_csrf(lead_api):
    response = lead_api.client.post("/api/projects", json={"key": "DVC", "name": "X"})
    assert response.status_code == 403


def test_list_only_accessible_projects(login_as, people, lead_api):
    _create(lead_api, key="AAA", name="Alfa", memberIds=[str(people["dev"].id)])
    _create(lead_api, key="BBB", name="Beta")
    admin = login_as(people["admin"])
    _create(admin, key="CCC", name="Gama")

    dev_list = login_as(people["dev"]).get("/api/projects").json()
    assert [item["key"] for item in dev_list["items"]] == ["AAA"]
    assert dev_list["total"] == 1

    lead_list = lead_api.get("/api/projects").json()
    assert [item["key"] for item in lead_list["items"]] == ["AAA", "BBB"]

    admin_list = admin.get("/api/projects", params={"sort": "-key"}).json()
    assert [item["key"] for item in admin_list["items"]] == ["CCC", "BBB", "AAA"]


def test_list_pagination_filters_and_search(lead_api):
    for index in range(5):
        _create(lead_api, key=f"P{index}", name=f"Projeto {index}")
    project = lead_api.get("/api/projects", params={"q": "P3"}).json()["items"][0]
    lead_api.post(f"/api/projects/{project['id']}/archive", json={"version": 1})

    page = lead_api.get("/api/projects", params={"page": 2, "pageSize": 2}).json()
    assert page["total"] == 4
    assert [item["key"] for item in page["items"]] == ["P2", "P4"]

    with_archived = lead_api.get("/api/projects", params={"includeArchived": "true"}).json()
    assert with_archived["total"] == 5
    archived = lead_api.get("/api/projects", params={"status": "archived"}).json()
    assert [item["key"] for item in archived["items"]] == ["P3"]

    assert lead_api.get("/api/projects", params={"q": "projeto 1"}).json()["total"] == 1
    assert lead_api.get("/api/projects", params={"q": ".*"}).json()["total"] == 0
    assert lead_api.get("/api/projects", params={"pageSize": 101}).status_code == 422
    assert lead_api.get("/api/projects", params={"sort": "memberIds"}).status_code == 422


def test_get_project_hides_inaccessible_projects(login_as, people, lead_api):
    project = _create(lead_api).json()
    other_lead = login_as(people["lead2"])

    assert lead_api.get(f"/api/projects/{project['id']}").status_code == 200
    assert other_lead.get(f"/api/projects/{project['id']}").status_code == 404
    assert lead_api.get(f"/api/projects/{ObjectId()}").status_code == 404
    assert lead_api.get("/api/projects/invalido").status_code == 404


def test_update_project(lead_api, people, indexed_db: Database):
    project = _create(lead_api).json()
    url = f"/api/projects/{project['id']}"

    response = lead_api.patch(
        url,
        json={
            "version": 1,
            "name": "Novo nome",
            "priority": "high",
            "status": "on_hold",
            "settings": {"sprintDurationDays": 10},
            "leadUserId": str(people["lead2"].id),
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Novo nome"
    assert body["priority"] == "high"
    assert body["status"] == "on_hold"
    assert body["settings"]["sprintDurationDays"] == 10
    assert body["lead"]["id"] == str(people["lead2"].id)
    assert body["memberCount"] == 2
    assert body["version"] == 2
    assert body["canManage"] is False

    audit = indexed_db.audit_logs.find_one({"action": "project.updated"})
    assert audit["details"]["changes"]["name"] == {"from": "VCCTeamForge", "to": "Novo nome"}


def test_update_rules(login_as, lead_api, people):
    project = _create(lead_api, memberIds=[str(people["dev"].id)]).json()
    url = f"/api/projects/{project['id']}"

    assert login_as(people["dev"]).patch(url, json={"version": 1, "name": "X"}).status_code == 403
    assert lead_api.patch(url, json={"version": 1, "key": "NEW"}).status_code == 422
    assert lead_api.patch(url, json={"version": 1, "status": "archived"}).status_code == 422
    assert lead_api.patch(url, json={"version": 1, "leadUserId": None}).status_code == 422
    assert (
        lead_api.patch(
            url, json={"version": 1, "targetDate": "2020-01-01", "startDate": "2021-01-01"}
        ).status_code
        == 422
    )

    assert lead_api.patch(url, json={"version": 1, "name": "A"}).status_code == 200
    stale = lead_api.patch(url, json={"version": 1, "name": "B"})
    assert stale.status_code == 409
    assert stale.json()["currentVersion"] == 2

    admin = login_as(people["admin"])
    assert admin.patch(url, json={"version": 2, "description": "admin"}).status_code == 200


def test_archive_and_restore(lead_api, people, indexed_db: Database):
    project = _create(lead_api, status="on_hold").json()
    url = f"/api/projects/{project['id']}"

    archived = lead_api.post(f"{url}/archive", json={"version": 1})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archivedAt"]
    assert archived.json()["canManage"] is False

    assert lead_api.patch(url, json={"version": 2, "name": "X"}).status_code == 422
    assert (
        lead_api.post(
            f"{url}/members", json={"version": 2, "userId": str(people["dev"].id)}
        ).status_code
        == 422
    )
    assert lead_api.post(f"{url}/archive", json={"version": 2}).status_code == 422

    restored = lead_api.post(f"{url}/restore", json={"version": 2})
    assert restored.status_code == 200
    assert restored.json()["status"] == "on_hold"
    assert restored.json()["archivedAt"] is None
    actions = [log["action"] for log in indexed_db.audit_logs.find().sort("createdAt", 1)]
    assert actions[-2:] == ["project.archived", "project.restored"]


def test_members(login_as, lead_api, people, indexed_db: Database):
    project = _create(lead_api).json()
    url = f"/api/projects/{project['id']}/members"
    dev = login_as(people["dev"])
    assert dev.get(f"/api/projects/{project['id']}").status_code == 404

    added = lead_api.post(url, json={"version": 1, "userId": str(people["dev"].id)})
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["version"] == 2
    assert [(member["name"], member["isLead"]) for member in body["members"]] == [
        ("Lead", True),
        ("Dev", False),
    ]
    assert dev.get(f"/api/projects/{project['id']}").status_code == 200
    assert dev.get(url).json()["canManage"] is False

    again = lead_api.post(url, json={"version": 2, "userId": str(people["dev"].id)})
    assert again.json()["version"] == 2
    assert (
        lead_api.post(url, json={"version": 1, "userId": str(people["qa"].id)}).status_code == 409
    )
    assert (
        lead_api.post(url, json={"version": 2, "userId": str(people["inactive"].id)}).status_code
        == 422
    )
    assert lead_api.post(url, json={"version": 2, "userId": str(ObjectId())}).status_code == 422
    assert dev.post(url, json={"version": 2, "userId": str(people["qa"].id)}).status_code == 403

    assert lead_api.delete(f"{url}/{people['lead'].id}", params={"version": 2}).status_code == 422
    removed = lead_api.delete(f"{url}/{people['dev'].id}", params={"version": 2})
    assert removed.status_code == 200
    assert [member["name"] for member in removed.json()["members"]] == ["Lead"]
    assert dev.get(f"/api/projects/{project['id']}").status_code == 404

    actions = {log["action"] for log in indexed_db.audit_logs.find()}
    assert {"project.member_added", "project.member_removed"} <= actions


def test_search_users_for_member_picker(login_as, lead_api, people):
    response = lead_api.get("/api/users", params={"q": "de"})
    assert response.status_code == 200
    names = [user["name"] for user in response.json()]
    assert names == ["Dev"]
    assert "passwordHash" not in response.text
    assert login_as(people["dev"]).get("/api/users").status_code == 403
    all_active = lead_api.get("/api/users").json()
    assert "Inactive" not in [user["name"] for user in all_active]
