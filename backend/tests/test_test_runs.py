import io
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo.database import Database

from app.domain.permissions import Role

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "qa": make_user("Qa", Role.QA),
        "qa2": make_user("Qa2", Role.QA),
        "outsider": make_user("Outsider", Role.QA),
    }


@pytest.fixture
def apis(login_as, people):
    return {name: login_as(user) for name, user in people.items()}


@pytest.fixture
def project(apis, people):
    members = [str(people[name].id) for name in ("dev", "qa", "qa2")]
    response = apis["lead"].post(
        "/api/projects", json={"key": "DVC", "name": "Projeto", "memberIds": members}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _case(api, project, **overrides):
    body = {
        "projectId": project["id"],
        "title": "Login com credenciais válidas",
        "preconditions": "Utilizador ativo",
        "steps": [{"action": "Abrir a página de login"}, {"action": "Submeter credenciais"}],
        "expectedResult": "Entra na aplicação",
        "priority": "high",
    } | overrides
    response = api.post("/api/test-cases", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def test_case(apis, project):
    return _case(apis["qa"], project)


@pytest.fixture
def plan(apis, project, test_case):
    response = apis["qa"].post(
        "/api/test-plans",
        json={
            "projectId": project["id"],
            "name": "Regressão 1.0",
            "testCaseIds": [test_case["id"]],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _run(api, test_case, plan=None, **overrides):
    body = {"testCaseId": test_case["id"], "result": "pass"} | overrides
    if plan is not None:
        body["testPlanId"] = plan["id"]
    return api.post("/api/test-runs", json=body)


def _upload(api, run, name="ecrã.png", content=PNG, content_type="image/png"):
    return api.post(
        f"/api/test-runs/{run['id']}/evidences",
        files={"file": (name, io.BytesIO(content), content_type)},
    )


# Registo -----------------------------------------------------------------------------------


def test_qa_records_run_with_snapshot_and_audit(apis, test_case, plan, indexed_db: Database):
    response = _run(
        apis["qa"],
        test_case,
        plan,
        result="fail",
        actualResult="  Erro 500  ",
        environment=" staging ",
        notes="Firefox",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["testCaseKey"] == test_case["key"]
    assert body["testCaseTitle"] == test_case["title"]
    assert body["testPlanName"] == "Regressão 1.0"
    assert body["result"] == "fail"
    assert body["actualResult"] == "Erro 500" and body["environment"] == "staging"
    assert body["executedBy"]["name"] == "Qa"
    assert body["version"] == 1 and body["bugCount"] == 0 and body["evidenceCount"] == 0
    assert body["canEdit"] is True and body["canCreateBug"] is True

    audit = indexed_db.audit_logs.find_one({"action": "test_run.created"})
    assert audit["entityId"] == ObjectId(body["id"])
    assert audit["details"]["result"] == "fail"

    # Renomear o caso não altera o snapshot da execução.
    apis["qa"].patch(f"/api/test-cases/{test_case['id']}", json={"version": 1, "title": "Novo"})
    assert (
        apis["dev"].get(f"/api/test-runs/{body['id']}").json()["testCaseTitle"]
        == (test_case["title"])
    )


def test_run_validations(apis, project, test_case, plan):
    qa = apis["qa"]
    deprecated = _case(qa, project, status="deprecated")
    other = _case(qa, project, title="Outro caso")
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    cases = [
        ({"testCaseId": deprecated["id"], "result": "pass"}, "testCaseId"),
        ({"testCaseId": "nao-e-id", "result": "pass"}, "testCaseId"),
        ({"testCaseId": str(ObjectId()), "result": "pass"}, "testCaseId"),
        ({"testCaseId": other["id"], "result": "pass", "testPlanId": plan["id"]}, "testPlanId"),
        ({"testCaseId": test_case["id"], "result": "pass", "testPlanId": "x"}, "testPlanId"),
        ({"testCaseId": test_case["id"], "result": "pass", "executedAt": future}, "executedAt"),
    ]
    for body, field in cases:
        response = qa.post("/api/test-runs", json=body)
        assert response.status_code == 422, (body, response.text)
        assert response.json().get("field") == field, body

    invalid = qa.post("/api/test-runs", json={"testCaseId": test_case["id"], "result": "ok"})
    assert invalid.status_code == 422

    closed = qa.patch(f"/api/test-plans/{plan['id']}", json={"version": 1, "status": "closed"})
    assert closed.status_code == 200, closed.text
    response = _run(qa, test_case, plan)
    assert response.status_code == 422 and response.json()["field"] == "testPlanId"


def test_run_permissions(apis, test_case):
    assert _run(apis["dev"], test_case).status_code == 403
    assert _run(apis["lead"], test_case).status_code == 403
    outsider = _run(apis["outsider"], test_case)
    assert outsider.status_code == 422 and outsider.json()["field"] == "testCaseId"
    assert _run(apis["admin"], test_case).status_code == 201

    run = _run(apis["qa"], test_case).json()
    assert apis["outsider"].get(f"/api/test-runs/{run['id']}").status_code == 404
    assert apis["dev"].get(f"/api/test-runs/{run['id']}").json()["canEdit"] is False
    assert apis["dev"].get("/api/test-runs/nao-e-id").status_code == 404


def test_update_run_with_version_and_permissions(apis, test_case, indexed_db: Database):
    run = _run(apis["qa"], test_case).json()
    url = f"/api/test-runs/{run['id']}"

    assert apis["dev"].patch(url, json={"version": 1, "result": "fail"}).status_code == 403

    response = apis["qa"].patch(url, json={"version": 1, "result": "fail", "notes": "Falhou"})
    assert response.status_code == 200, response.text
    assert response.json()["result"] == "fail" and response.json()["version"] == 2

    stale = apis["qa"].patch(url, json={"version": 1, "result": "blocked"})
    assert stale.status_code == 409 and stale.json()["currentVersion"] == 2
    assert apis["qa"].patch(url, json={"version": 2, "result": None}).status_code == 422

    # Quem tem tests:manage pode corrigir execuções de outros.
    assert apis["qa2"].patch(url, json={"version": 2, "result": "blocked"}).status_code == 200

    audit = indexed_db.audit_logs.find_one({"action": "test_run.updated"})
    assert audit["details"]["changes"]["result"] == {"from": "pass", "to": "fail"}
    assert audit["details"]["changes"]["notes"] == {"changed": True}


def test_list_runs_with_filters(apis, project, test_case, plan, people):
    other = _case(apis["qa"], project, title="Outro")
    _run(apis["qa"], test_case, plan, result="fail")
    _run(apis["qa2"], other, result="pass")
    _run(apis["qa"], test_case, result="blocked")

    def ids(api, query=""):
        response = api.get(f"/api/test-runs?projectId={project['id']}{query}")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        return response.json()

    assert ids(apis["dev"])["total"] == 3
    assert ids(apis["dev"], f"&testCaseId={test_case['id']}")["total"] == 2
    assert [r["result"] for r in ids(apis["dev"], f"&testPlanId={plan['id']}")["items"]] == ["fail"]
    assert ids(apis["dev"], "&result=pass&result=blocked")["total"] == 2
    mine = ids(apis["qa2"], "&executedBy=me")
    assert mine["total"] == 1 and mine["items"][0]["testCaseKey"] == other["key"]
    assert ids(apis["dev"], f"&executedBy={people['qa'].id}")["total"] == 2
    assert apis["dev"].get(
        f"/api/test-runs?projectId={project['id']}&testCaseId=x"
    ).status_code == (422)
    assert apis["outsider"].get(f"/api/test-runs?projectId={project['id']}").status_code == 404


# Evidências --------------------------------------------------------------------------------


def test_evidence_upload_download_and_delete(apis, test_case, api_settings, indexed_db: Database):
    run = _run(apis["qa"], test_case, result="fail").json()
    assert _upload(apis["dev"], run).status_code == 403

    response = _upload(apis["qa"], run)
    assert response.status_code == 201, response.text
    evidence = response.json()
    assert evidence["originalName"] == "ecrã.png" and evidence["isImage"] is True
    assert evidence["testRunId"] == run["id"] and evidence["canDelete"] is True

    document = indexed_db.attachments.find_one({"_id": ObjectId(evidence["id"])})
    assert document["issueId"] is None and document["testRunId"] == ObjectId(run["id"])
    assert (api_settings.attachments_path / document["storageKey"]).read_bytes() == PNG

    listing = apis["dev"].get(f"/api/test-runs/{run['id']}/evidences").json()
    assert [item["id"] for item in listing] == [evidence["id"]]
    assert listing[0]["canDelete"] is False
    assert apis["dev"].get(f"/api/test-runs/{run['id']}").json()["evidenceCount"] == 1

    content_url = f"/api/test-runs/{run['id']}/evidences/{evidence['id']}/content"
    download = apis["dev"].get(content_url)
    assert download.status_code == 200 and download.content == PNG
    assert download.headers["content-disposition"].startswith("attachment")
    assert download.headers["x-content-type-options"] == "nosniff"
    assert (
        apis["dev"]
        .get(f"{content_url}?inline=true")
        .headers["content-disposition"]
        .startswith("inline")
    )
    assert apis["outsider"].get(content_url).status_code == 404

    # As evidências não aparecem como anexos de issues.
    other_run = _run(apis["qa"], test_case).json()
    wrong = f"/api/test-runs/{other_run['id']}/evidences/{evidence['id']}/content"
    assert apis["dev"].get(wrong).status_code == 404

    bad = _upload(apis["qa"], run, name="script.exe", content=b"MZ", content_type="text/plain")
    assert bad.status_code == 422

    delete_url = f"/api/test-runs/{run['id']}/evidences/{evidence['id']}"
    assert apis["dev"].delete(delete_url).status_code == 403
    assert apis["qa"].delete(delete_url).status_code == 204
    assert apis["dev"].get(f"/api/test-runs/{run['id']}/evidences").json() == []
    assert apis["dev"].get(content_url).status_code == 404
    assert not (api_settings.attachments_path / document["storageKey"]).exists()
    actions = {log["action"] for log in indexed_db.audit_logs.find()}
    assert {"test_run_evidence.created", "test_run_evidence.deleted"} <= actions


# Bugs a partir de falhas -------------------------------------------------------------------


def test_create_bug_from_failed_run(apis, test_case, plan, people, indexed_db: Database):
    passed = _run(apis["qa"], test_case, plan).json()
    response = apis["qa"].post(f"/api/test-runs/{passed['id']}/bugs", json={})
    assert response.status_code == 422 and response.json()["field"] == "result"
    assert apis["qa"].get(f"/api/test-runs/{passed['id']}").json()["canCreateBug"] is False

    failed = _run(
        apis["qa"], test_case, plan, result="fail", actualResult="Erro 500", environment="staging"
    ).json()
    assert apis["lead"].post(f"/api/test-runs/{failed['id']}/bugs", json={}).status_code == 201
    response = apis["dev"].post(
        f"/api/test-runs/{failed['id']}/bugs",
        json={"title": "Login devolve 500", "assigneeId": str(people["dev"].id)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["bugCount"] == 2 and body["version"] == 3
    assert [bug["title"] for bug in body["bugs"]][1] == "Login devolve 500"
    assert body["bugs"][0]["title"].startswith(f"Falha em {test_case['key']}")

    bug = indexed_db.issues.find_one({"_id": ObjectId(body["bugs"][0]["id"])})
    assert bug["type"] == "bug" and bug["priority"] == "high"
    assert "Erro 500" in bug["description"] and "staging" in bug["description"]
    assert "Abrir a página de login" in bug["description"]
    assert indexed_db.audit_logs.count_documents({"action": "test_run.bug_created"}) == 2

    assert apis["outsider"].post(f"/api/test-runs/{failed['id']}/bugs", json={}).status_code == (
        404
    )


# Progresso do plano ------------------------------------------------------------------------


def test_plan_progress_with_regression_and_pass_rate(apis, project, test_case, people):
    qa = apis["qa"]
    second = _case(qa, project, title="Logout")
    third = _case(qa, project, title="Recuperar password")
    plan = qa.post(
        "/api/test-plans",
        json={
            "projectId": project["id"],
            "name": "Sprint 1",
            "testCaseIds": [test_case["id"], second["id"], third["id"]],
        },
    ).json()
    earlier = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert _run(qa, test_case, plan, result="pass", executedAt=earlier).status_code == 201
    assert _run(qa, test_case, plan, result="fail").status_code == 201
    assert _run(qa, second, plan, result="pass").status_code == 201
    # Execuções sem plano não contam para o progresso.
    assert _run(qa, third, result="fail").status_code == 201

    response = apis["dev"].get(f"/api/test-plans/{plan['id']}/progress")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totalCases"] == 3 and body["executedCases"] == 2
    assert body["counts"]["pass"] == 1 and body["counts"]["fail"] == 1
    assert body["counts"]["not_run"] == 1
    assert body["passRate"] == 0.5 and body["regressions"] == 1
    first_case = body["cases"][0]
    assert first_case["testCase"]["id"] == test_case["id"]
    assert first_case["lastResult"] == "fail" and first_case["previousResult"] == "pass"
    assert first_case["regression"] is True
    assert first_case["lastExecutedBy"]["id"] == str(people["qa"].id)
    assert body["cases"][2]["lastResult"] == "not_run" and body["cases"][2]["lastRunId"] is None

    assert apis["outsider"].get(f"/api/test-plans/{plan['id']}/progress").status_code == 404
    assert apis["dev"].get(f"/api/test-plans/{ObjectId()}/progress").status_code == 404


def test_archived_project_blocks_runs(apis, project, test_case):
    run = _run(apis["qa"], test_case).json()
    archived = apis["lead"].post(
        f"/api/projects/{project['id']}/archive", json={"version": project["version"]}
    )
    assert archived.status_code == 200, archived.text
    assert _run(apis["qa"], test_case).status_code == 422
    url = f"/api/test-runs/{run['id']}"
    assert apis["qa"].patch(url, json={"version": 1, "result": "fail"}).status_code == 422
    assert apis["qa"].get(url).json()["canEdit"] is False
