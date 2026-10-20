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
        "outsider": make_user("Outsider", Role.QA),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


@pytest.fixture
def qa_api(login_as, people):
    return login_as(people["qa"])


def _project(api, people, key):
    response = api.post(
        "/api/projects",
        json={
            "key": key,
            "name": f"Projeto {key}",
            "memberIds": [str(people["dev"].id), str(people["qa"].id)],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def project(lead_api, people):
    return _project(lead_api, people, "DVC")


@pytest.fixture
def issue(lead_api, project):
    response = lead_api.post(
        "/api/issues", json={"projectId": project["id"], "type": "story", "title": "Login"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _case(api, project, **overrides):
    body = {
        "projectId": project["id"],
        "title": "Login com credenciais válidas",
        "preconditions": "Utilizador ativo",
        "steps": [
            {"action": "Abrir a página de login", "expectedResult": "Formulário visível"},
            {"action": "Submeter credenciais válidas"},
        ],
        "expectedResult": "Entra na aplicação",
    } | overrides
    return api.post("/api/test-cases", json=body)


def _plan(api, project, **overrides):
    body = {"projectId": project["id"], "name": "Regressão 1.0"} | overrides
    return api.post("/api/test-plans", json=body)


# Casos de teste ----------------------------------------------------------------------------


def test_create_test_case(qa_api, project, issue, people, indexed_db: Database):
    response = _case(qa_api, project, issueIds=[issue["id"]], labels=[" Login ", "login"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["key"] == "TC-1"
    assert body["status"] == "draft"
    assert body["priority"] == "medium"
    assert body["labels"] == ["login"]
    assert body["stepCount"] == 2
    assert body["steps"][1] == {"action": "Submeter credenciais válidas", "expectedResult": ""}
    assert body["issues"] == [
        {
            "id": issue["id"],
            "key": issue["key"],
            "title": "Login",
            "type": "story",
            "status": "todo",
        }
    ]
    assert body["canEdit"] is True
    assert _case(qa_api, project).json()["key"] == "TC-2"

    document = indexed_db.test_cases.find_one({"_id": ObjectId(body["id"])})
    assert document["issueIds"] == [ObjectId(issue["id"])]
    assert document["createdBy"] == people["qa"].id
    audit = indexed_db.audit_logs.find_one({"action": "test_case.created"})
    assert audit["entityId"] == document["_id"]
    assert audit["details"] == {
        "projectKey": "DVC",
        "key": "TC-1",
        "title": "Login com credenciais válidas",
    }


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"steps": []}, "steps"),
        ({"steps": [{"action": "   "}]}, "steps"),
        ({"title": "   "}, "title"),
        ({"issueIds": ["nao-e-id"]}, "issueIds"),
        ({"issueIds": [str(ObjectId())]}, "issueIds"),
        ({"labels": ["x" * 41]}, "labels"),
        ({"projectId": "nao-e-id"}, "projectId"),
        ({"projectId": str(ObjectId())}, "projectId"),
    ],
)
def test_create_test_case_validation(qa_api, project, overrides, field):
    response = _case(qa_api, project, **overrides)

    assert response.status_code == 422, response.text
    if field != "steps" or overrides["steps"]:
        assert response.json()["field"] == field


def test_issues_from_other_projects_cannot_be_linked(qa_api, lead_api, people, project):
    other = _project(lead_api, people, "OTR")
    foreign = lead_api.post(
        "/api/issues", json={"projectId": other["id"], "type": "bug", "title": "Outro"}
    ).json()

    response = _case(qa_api, project, issueIds=[foreign["id"]])

    assert response.status_code == 422
    assert response.json()["field"] == "issueIds"


def test_test_case_permissions(login_as, people, project, qa_api):
    test_case = _case(qa_api, project).json()

    dev_api = login_as(people["dev"])
    assert _case(dev_api, project).status_code == 403
    detail = dev_api.get(f"/api/test-cases/{test_case['id']}")
    assert detail.status_code == 200
    assert detail.json()["canEdit"] is False
    assert login_as(people["lead"]).post("/api/test-cases", json={}).status_code == 403

    outsider = login_as(people["outsider"])
    assert outsider.get(f"/api/test-cases/{test_case['id']}").status_code == 404
    assert outsider.get(f"/api/test-cases?projectId={project['id']}").status_code == 404
    assert _case(outsider, project).json()["field"] == "projectId"
    assert login_as(people["admin"]).get(f"/api/test-cases/{test_case['id']}").status_code == 200


def test_update_test_case(qa_api, project, issue, indexed_db: Database):
    test_case = _case(qa_api, project).json()

    response = qa_api.patch(
        f"/api/test-cases/{test_case['id']}",
        json={
            "version": 1,
            "title": "Login válido",
            "status": "ready",
            "priority": "high",
            "steps": [{"action": "Entrar", "expectedResult": "Dashboard"}],
            "issueIds": [issue["id"]],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Login válido"
    assert body["status"] == "ready"
    assert body["priority"] == "high"
    assert body["stepCount"] == 1
    assert body["issues"][0]["key"] == issue["key"]
    assert body["version"] == 2
    assert body["preconditions"] == "Utilizador ativo"
    audit = indexed_db.audit_logs.find_one({"action": "test_case.updated"})
    assert audit["details"]["changes"]["status"] == {"from": "draft", "to": "ready"}
    assert audit["details"]["changes"]["steps"] == {"changed": True}

    stale = qa_api.patch(f"/api/test-cases/{test_case['id']}", json={"version": 1, "title": "X"})
    assert stale.status_code == 409
    assert stale.json()["currentVersion"] == 2
    unchanged = qa_api.patch(
        f"/api/test-cases/{test_case['id']}", json={"version": 2, "title": "Login válido"}
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["version"] == 2
    assert (
        qa_api.patch(
            f"/api/test-cases/{test_case['id']}", json={"version": 2, "status": None}
        ).status_code
        == 422
    )


def test_list_test_cases_filters_and_sort(qa_api, project, issue):
    _case(qa_api, project, title="Login", priority="low", labels=["auth"])
    _case(qa_api, project, title="Logout", priority="critical", issueIds=[issue["id"]])
    _case(qa_api, project, title="Perfil", status="ready")
    base = f"/api/test-cases?projectId={project['id']}"

    def titles(query=""):
        response = qa_api.get(base + query)
        assert response.status_code == 200, response.text
        return [item["title"] for item in response.json()["items"]]

    assert titles() == ["Login", "Logout", "Perfil"]
    assert titles("&sort=-priority") == ["Logout", "Perfil", "Login"]
    assert titles("&status=ready") == ["Perfil"]
    assert titles("&priority=low&priority=critical") == ["Login", "Logout"]
    assert titles("&label=AUTH") == ["Login"]
    assert titles(f"&issueId={issue['id']}") == ["Logout"]
    assert titles("&q=log") == ["Login", "Logout"]
    assert titles("&q=tc-3") == ["Perfil"]
    page = qa_api.get(base + "&pageSize=1&page=2").json()
    assert page["total"] == 3
    assert page["items"][0]["key"] == "TC-2"
    assert "steps" not in page["items"][0]
    assert qa_api.get(base + "&issueId=xyz").json()["field"] == "issueId"
    assert qa_api.get("/api/test-cases").status_code == 422


def test_archived_project_is_read_only(lead_api, qa_api, project):
    test_case = _case(qa_api, project).json()
    lead_api.post(f"/api/projects/{project['id']}/archive", json={"version": project["version"]})

    assert _case(qa_api, project).status_code == 422
    response = qa_api.patch(f"/api/test-cases/{test_case['id']}", json={"version": 1, "title": "X"})
    assert response.status_code == 422
    assert qa_api.get(f"/api/test-cases/{test_case['id']}").json()["canEdit"] is False
    assert _plan(qa_api, project).status_code == 422


# Planos de teste ---------------------------------------------------------------------------


def test_create_test_plan(qa_api, project, issue, indexed_db: Database):
    first = _case(qa_api, project, title="Primeiro").json()
    second = _case(qa_api, project, title="Segundo").json()

    response = _plan(
        qa_api,
        project,
        description="Antes da release",
        testCaseIds=[second["id"], first["id"], second["id"]],
        issueIds=[issue["id"]],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["testCaseCount"] == 2
    assert [item["key"] for item in body["testCases"]] == ["TC-2", "TC-1"]
    assert body["issues"][0]["id"] == issue["id"]
    assert body["canEdit"] is True
    document = indexed_db.test_plans.find_one({"_id": ObjectId(body["id"])})
    assert document["nameKey"] == "regressão 1.0"
    assert indexed_db.audit_logs.find_one({"action": "test_plan.created"}) is not None

    duplicate = _plan(qa_api, project, name="  REGRESSÃO   1.0 ")
    assert duplicate.status_code == 409
    assert duplicate.json()["field"] == "name"


def test_test_plan_case_validation(qa_api, lead_api, people, project):
    deprecated = _case(qa_api, project, status="deprecated").json()
    other = _project(lead_api, people, "OTR")
    foreign = _case(qa_api, other).json()

    for ids in ([deprecated["id"]], [foreign["id"]], ["nao-e-id"], [str(ObjectId())]):
        response = _plan(qa_api, project, testCaseIds=ids)
        assert response.status_code == 422, ids
        assert response.json()["field"] == "testCaseIds"


def test_update_test_plan(qa_api, project, indexed_db: Database):
    test_case = _case(qa_api, project).json()
    plan = _plan(qa_api, project, testCaseIds=[test_case["id"]]).json()
    qa_api.patch(f"/api/test-cases/{test_case['id']}", json={"version": 1, "status": "deprecated"})
    new_case = _case(qa_api, project, title="Novo").json()
    url = f"/api/test-plans/{plan['id']}"

    # Um caso obsoleto que já estava no plano pode ficar.
    response = qa_api.patch(
        url,
        json={
            "version": 1,
            "name": "Regressão 1.1",
            "status": "active",
            "testCaseIds": [new_case["id"], test_case["id"]],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Regressão 1.1"
    assert body["status"] == "active"
    assert [item["title"] for item in body["testCases"]] == ["Novo", test_case["title"]]
    assert body["testCases"][1]["status"] == "deprecated"
    assert body["version"] == 2
    audit = indexed_db.audit_logs.find_one({"action": "test_plan.updated"})
    assert audit["details"]["changes"]["status"] == {"from": "draft", "to": "active"}
    assert audit["details"]["changes"]["testCaseIds"] == {"changed": True}

    assert qa_api.patch(url, json={"version": 1, "name": "X"}).status_code == 409
    closed = qa_api.patch(url, json={"version": 2, "status": "closed"})
    assert closed.status_code == 200
    blocked = qa_api.patch(url, json={"version": 3, "name": "Outro"})
    assert blocked.status_code == 422
    assert blocked.json()["field"] == "status"
    assert qa_api.patch(url, json={"version": 3, "status": "active"}).status_code == 200


def test_test_plan_permissions_and_list(login_as, people, project, qa_api):
    _plan(qa_api, project, name="Beta")
    _plan(qa_api, project, name="alfa", status="active")
    dev_api = login_as(people["dev"])
    base = f"/api/test-plans?projectId={project['id']}"

    assert _plan(dev_api, project, name="Gama").status_code == 403
    names = [item["name"] for item in dev_api.get(base + "&sort=name").json()["items"]]
    assert names == ["alfa", "Beta"]
    assert [item["name"] for item in dev_api.get(base).json()["items"]] == ["alfa", "Beta"]
    assert [item["name"] for item in dev_api.get(base + "&status=draft").json()["items"]] == [
        "Beta"
    ]
    assert [item["name"] for item in dev_api.get(base + "&q=ALF").json()["items"]] == ["alfa"]
    assert login_as(people["outsider"]).get(base).status_code == 404
    assert dev_api.get("/api/test-plans/nao-e-id").status_code == 404
