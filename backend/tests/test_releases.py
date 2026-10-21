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
def apis(login_as, people):
    return {name: login_as(user) for name, user in people.items()}


@pytest.fixture
def project(apis, people):
    members = [str(people[name].id) for name in ("dev", "qa")]
    response = apis["lead"].post(
        "/api/projects", json={"key": "REL", "name": "Projeto", "memberIds": members}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _issue(api, project, **overrides):
    body = {"projectId": project["id"], "type": "story", "title": "Funcionalidade"} | overrides
    response = api.post("/api/issues", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _finish(api, issue):
    url = f"/api/issues/{issue['id']}"
    for status in ("in_progress", "code_review", "testing", "done"):
        response = api.patch(url, json={"version": issue["version"], "status": status})
        assert response.status_code == 200, response.text
        issue = response.json()
    return issue


def _plan_with_case(api, project):
    case = api.post(
        "/api/test-cases",
        json={
            "projectId": project["id"],
            "title": "Login",
            "steps": [{"action": "Entrar"}],
            "expectedResult": "Entra",
        },
    ).json()
    plan = api.post(
        "/api/test-plans",
        json={"projectId": project["id"], "name": "Regressão", "testCaseIds": [case["id"]]},
    ).json()
    return case, plan


def _create(api, project, **overrides):
    return api.post("/api/releases", json={"projectId": project["id"], "name": "1.0.0"} | overrides)


def _transition(api, release, to, comment=""):
    return api.post(
        f"/api/releases/{release['id']}/transitions",
        json={"to": to, "comment": comment, "version": release["version"]},
    )


def _all_done(release):
    return [
        {"id": item["id"], "label": item["label"], "required": item["required"], "done": True}
        for item in release["checklist"]
    ]


def _without_criteria(api, release):
    response = api.patch(
        f"/api/releases/{release['id']}",
        json={
            "version": release["version"],
            "checklist": _all_done(release),
            "criteria": {"issuesDone": False, "testsPassed": False, "noOpenCriticalBugs": False},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# Criação e leitura -------------------------------------------------------------------------


def test_lead_creates_release_with_default_checklist_and_audit(apis, project, indexed_db: Database):
    story = _issue(apis["lead"], project)
    bug = _issue(apis["lead"], project, type="bug", priority="critical", title="Erro")
    _, plan = _plan_with_case(apis["qa"], project)

    response = _create(
        apis["lead"],
        project,
        name=" 1.4.0-rc.1 ",
        description="Primeira versão",
        notes="## Novidades",
        plannedDate="2026-11-30",
        issueIds=[story["id"], story["id"]],
        knownBugIds=[bug["id"]],
        testPlanIds=[plan["id"]],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "1.4.0-rc.1" and body["status"] == "draft"
    assert body["plannedDate"] == "2026-11-30" and body["releasedAt"] is None
    assert [issue["key"] for issue in body["issues"]] == [story["key"]]
    assert [issue["key"] for issue in body["knownBugs"]] == [bug["key"]]
    assert [item["name"] for item in body["testPlans"]] == ["Regressão"]
    assert [item["label"] for item in body["checklist"]] == [
        "Testes de regressão executados",
        "Notas de release revistas",
        "Bugs conhecidos documentados",
        "Plano de rollback definido",
    ]
    assert [item["required"] for item in body["checklist"]] == [True, True, True, False]
    assert body["criteria"] == {"issuesDone": True, "testsPassed": True, "noOpenCriticalBugs": True}
    assert body["canEdit"] is True and body["availableTransitions"] == ["ready_for_qa"]
    assert body["history"][0]["action"] == "created"
    assert body["history"][0]["user"]["name"] == "Lead"
    assert body["checklistTotal"] == 4 and body["checklistDone"] == 0

    quality = body["quality"]
    assert quality["issues"] == {"total": 1, "done": 0}
    assert quality["knownBugs"] == {"total": 1, "open": 1, "openCritical": 1}
    assert quality["tests"]["plans"] == 1 and quality["tests"]["totalCases"] == 1
    assert quality["ready"] is False
    assert {item["key"]: item["passed"] for item in quality["criteria"]} == {
        "issuesDone": False,
        "testsPassed": False,
        "noOpenCriticalBugs": False,
    }

    audit = indexed_db["audit_logs"].find_one({"action": "release.created"})
    assert audit is not None and audit["details"]["name"] == "1.4.0-rc.1"


def test_new_release_inherits_checklist_from_latest(apis, project):
    first = _create(
        apis["lead"],
        project,
        checklist=[{"label": "Smoke test", "required": True, "done": True}],
    ).json()
    assert first["checklist"][0]["done"] is True
    assert first["checklist"][0]["doneBy"]["name"] == "Lead"

    second = _create(apis["lead"], project, name="1.1.0").json()

    assert [(item["label"], item["required"], item["done"]) for item in second["checklist"]] == [
        ("Smoke test", True, False)
    ]
    assert second["checklist"][0]["id"] != first["checklist"][0]["id"]


def test_release_validation(apis, project):
    assert _create(apis["lead"], project).status_code == 201

    duplicate = _create(apis["lead"], project, name="1.0.0")
    assert duplicate.status_code == 409 and duplicate.json()["field"] == "name"
    invalid = _create(apis["lead"], project, name="versão 1")
    assert invalid.status_code == 422 and invalid.json()["field"] == "name"

    story = _issue(apis["lead"], project)
    not_bug = _create(apis["lead"], project, name="2.0", knownBugIds=[story["id"]])
    assert not_bug.status_code == 422 and not_bug.json()["field"] == "knownBugIds"

    other = apis["admin"].post("/api/projects", json={"key": "OUT", "name": "Outro"}).json()
    foreign_plan = apis["admin"].post(
        "/api/test-plans", json={"projectId": other["id"], "name": "Plano"}
    )
    assert foreign_plan.status_code == 201, foreign_plan.text
    response = _create(apis["lead"], project, name="2.0", testPlanIds=[foreign_plan.json()["id"]])
    assert response.status_code == 422 and response.json()["field"] == "testPlanIds"
    response = _create(apis["lead"], project, name="2.0", issueIds=["x"])
    assert response.status_code == 422 and response.json()["field"] == "issueIds"


def test_release_permissions_and_listing(apis, project):
    release = _create(apis["lead"], project, name="1.2.0").json()
    _create(apis["lead"], project, name="1.3.0")

    for name in ("dev", "qa"):
        assert _create(apis[name], project, name="9.9").status_code == 403
        patch = apis[name].patch(
            f"/api/releases/{release['id']}", json={"version": 1, "notes": "x"}
        )
        assert patch.status_code == 403
        assert _transition(apis[name], release, "ready_for_qa").status_code == 403
        detail = apis[name].get(f"/api/releases/{release['id']}").json()
        assert detail["canEdit"] is False and detail["availableTransitions"] == []

    assert apis["outsider"].get(f"/api/releases/{release['id']}").status_code == 404
    listing = apis["outsider"].get(f"/api/releases?projectId={project['id']}")
    assert listing.status_code == 404

    page = apis["dev"].get(f"/api/releases?projectId={project['id']}").json()
    assert [item["name"] for item in page["items"]] == ["1.3.0", "1.2.0"]
    assert page["total"] == 2
    filtered = apis["dev"].get(f"/api/releases?projectId={project['id']}&q=1.2").json()
    assert [item["name"] for item in filtered["items"]] == ["1.2.0"]
    by_status = apis["dev"].get(f"/api/releases?projectId={project['id']}&status=released")
    assert by_status.json()["total"] == 0


# Edição ------------------------------------------------------------------------------------


def test_update_tracks_checklist_history_and_version(apis, project, indexed_db: Database):
    release = _create(apis["lead"], project).json()
    url = f"/api/releases/{release['id']}"
    item = release["checklist"][0]

    response = apis["lead"].patch(
        url,
        json={
            "version": 1,
            "name": "1.0.1",
            "plannedDate": "2026-12-01",
            "checklist": [
                {"id": item["id"], "label": item["label"], "required": True, "done": True},
                {"label": "Novo item", "required": False},
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "1.0.1" and body["version"] == 2
    assert [entry["label"] for entry in body["checklist"]] == [item["label"], "Novo item"]
    assert body["checklist"][0]["id"] == item["id"]
    assert body["checklist"][0]["doneBy"]["name"] == "Lead"
    assert body["checklist"][0]["doneAt"] is not None
    assert body["history"][0]["action"] == "updated"
    assert set(body["history"][0]["fields"]) == {"name", "plannedDate", "checklist"}

    stale = apis["lead"].patch(url, json={"version": 1, "notes": "x"})
    assert stale.status_code == 409 and stale.json()["currentVersion"] == 2

    unchanged = apis["lead"].patch(url, json={"version": 2, "name": "1.0.1"})
    assert unchanged.status_code == 200 and unchanged.json()["version"] == 2

    unchecked = (
        apis["lead"]
        .patch(
            url,
            json={
                "version": 2,
                "checklist": [{"id": item["id"], "label": item["label"], "required": True}],
            },
        )
        .json()
    )
    assert unchecked["checklist"][0]["done"] is False
    assert unchecked["checklist"][0]["doneBy"] is None

    audit = indexed_db["audit_logs"].find_one({"action": "release.updated"})
    assert audit is not None and "name" in audit["details"]["changes"]


# Workflow ----------------------------------------------------------------------------------


def test_approval_requires_checklist_and_criteria(apis, project):
    story = _issue(apis["lead"], project)
    bug = _issue(apis["lead"], project, type="bug", priority="critical", title="Erro")
    case, plan = _plan_with_case(apis["qa"], project)
    release = _create(
        apis["lead"],
        project,
        issueIds=[story["id"]],
        knownBugIds=[bug["id"]],
        testPlanIds=[plan["id"]],
    ).json()

    release = _transition(apis["lead"], release, "ready_for_qa").json()
    assert release["status"] == "ready_for_qa"
    assert release["availableTransitions"] == ["approved", "draft"]

    blocked = _transition(apis["lead"], release, "approved")
    assert blocked.status_code == 422 and blocked.json()["field"] == "checklist"

    release = (
        apis["lead"]
        .patch(
            f"/api/releases/{release['id']}",
            json={"version": release["version"], "checklist": _all_done(release)},
        )
        .json()
    )
    blocked = _transition(apis["lead"], release, "approved")
    assert blocked.status_code == 422 and blocked.json()["field"] == "criteria"
    assert "Sem bugs críticos em aberto" in blocked.json()["detail"]

    _finish(apis["lead"], story)
    _finish(apis["lead"], bug)
    run = apis["qa"].post(
        "/api/test-runs",
        json={"testCaseId": case["id"], "testPlanId": plan["id"], "result": "pass"},
    )
    assert run.status_code == 201, run.text

    release = apis["lead"].get(f"/api/releases/{release['id']}").json()
    assert release["quality"]["ready"] is True
    assert release["quality"]["tests"]["passRate"] == 1.0
    approved = _transition(apis["lead"], release, "approved")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["canEdit"] is False


def test_workflow_reject_reopen_release_and_history(apis, project, indexed_db: Database):
    release = _without_criteria(apis["lead"], _create(apis["lead"], project).json())

    assert _transition(apis["lead"], release, "released").json()["field"] == "to"
    release = _transition(apis["lead"], release, "ready_for_qa").json()

    no_comment = _transition(apis["lead"], release, "draft")
    assert no_comment.status_code == 422 and no_comment.json()["field"] == "comment"
    release = _transition(apis["lead"], release, "draft", "Faltam notas").json()
    assert release["status"] == "draft"

    release = _transition(apis["lead"], release, "ready_for_qa").json()
    release = _transition(apis["lead"], release, "approved").json()
    patch = apis["lead"].patch(
        f"/api/releases/{release['id']}", json={"version": release["version"], "notes": "x"}
    )
    assert patch.status_code == 422

    release = _transition(apis["lead"], release, "draft", "Bug encontrado").json()
    release = _transition(apis["lead"], release, "ready_for_qa").json()
    release = _transition(apis["lead"], release, "approved").json()
    stale = apis["lead"].post(
        f"/api/releases/{release['id']}/transitions",
        json={"to": "released", "version": release["version"] - 1},
    )
    assert stale.status_code == 409

    released = _transition(apis["lead"], release, "released")
    assert released.status_code == 200, released.text
    release = released.json()
    assert release["status"] == "released" and release["releasedAt"] is not None
    assert release["availableTransitions"] == [] and release["canEdit"] is False
    assert _transition(apis["lead"], release, "draft", "x").status_code == 422

    actions = [entry["action"] for entry in release["history"]]
    assert actions == [
        "released",
        "approved",
        "submitted",
        "reopened",
        "approved",
        "submitted",
        "rejected",
        "submitted",
        "updated",
        "created",
    ]
    rejected = release["history"][6]
    assert rejected["comment"] == "Faltam notas"
    assert rejected["fromStatus"] == "ready_for_qa" and rejected["toStatus"] == "draft"

    stored = indexed_db["audit_logs"].count_documents(
        {"action": "release.transitioned", "entityId": ObjectId(release["id"])}
    )
    assert stored == 8


def test_archived_project_is_read_only(apis, project):
    release = _create(apis["lead"], project).json()
    current = apis["lead"].get(f"/api/projects/{project['id']}").json()
    archived = apis["lead"].post(
        f"/api/projects/{project['id']}/archive", json={"version": current["version"]}
    )
    assert archived.status_code == 200, archived.text

    assert _create(apis["lead"], project, name="2.0").status_code == 422
    assert _transition(apis["lead"], release, "ready_for_qa").status_code == 422
    detail = apis["lead"].get(f"/api/releases/{release['id']}").json()
    assert detail["canEdit"] is False and detail["availableTransitions"] == []
