from typing import Any

import pytest
from bson import ObjectId
from pymongo.database import Database

from app.domain.permissions import Role
from app.services.issues import SUMMARY_PROJECTION


@pytest.fixture
def people(make_user):
    return {
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "other": make_user("Other", Role.DEVELOPER),
        "admin": make_user("Admin", Role.ADMIN),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


def _project(api, key, members):
    response = api.post("/api/projects", json={"key": key, "name": key, "memberIds": members})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def projects(lead_api, people):
    main = _project(lead_api, "DVC", [str(people["dev"].id)])
    other = _project(lead_api, "OTR", [str(people["other"].id)])
    return main, other


def _issue(api, project, **fields) -> dict[str, Any]:
    body = {"projectId": project["id"], "type": "story", "title": "Issue"} | fields
    response = api.post("/api/issues", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def dataset(lead_api, projects, people):
    main, other = projects
    dev = str(people["dev"].id)
    issues = {
        "login": _issue(
            lead_api, main, title="Login (SSO)", priority="high", labels=["auth"], assigneeId=dev
        ),
        "bug": _issue(lead_api, main, type="bug", title="Erro 500", priority="critical"),
        "epic": _issue(lead_api, main, type="epic", title="Pagamentos", labels=["billing"]),
        "doc": _issue(lead_api, main, type="task", title="Docs", priority="low", labels=["docs"]),
        "foreign": _issue(lead_api, other, title="Login noutro projeto"),
    }
    blocked = issues["doc"]
    response = lead_api.patch(
        f"/api/issues/{blocked['id']}",
        json={"version": blocked["version"], "blocked": True, "blockReason": "À espera"},
    )
    assert response.status_code == 200, response.text
    moved = issues["login"]
    response = lead_api.patch(
        f"/api/issues/{moved['id']}", json={"version": moved["version"], "status": "in_progress"}
    )
    assert response.status_code == 200, response.text
    return issues


def _keys(api, query: str) -> list[str]:
    response = api.get(f"/api/issues?{query}")
    assert response.status_code == 200, response.text
    return [item["key"] for item in response.json()["items"]]


def test_each_filter(lead_api, projects, dataset, people):
    pid = f"projectId={projects[0]['id']}"
    assert _keys(lead_api, f"{pid}&status=in_progress") == ["DVC-1"]
    assert _keys(lead_api, f"{pid}&status=todo&status=in_progress") == [
        "DVC-4",
        "DVC-3",
        "DVC-2",
        "DVC-1",
    ]
    assert _keys(lead_api, f"{pid}&priority=critical&priority=low") == ["DVC-4", "DVC-2"]
    assert _keys(lead_api, f"{pid}&type=bug") == ["DVC-2"]
    assert _keys(lead_api, f"{pid}&assigneeId={people['dev'].id}") == ["DVC-1"]
    assert _keys(lead_api, f"{pid}&assigneeId=none") == ["DVC-4", "DVC-3", "DVC-2"]
    assert _keys(lead_api, f"{pid}&label=Auth&label=docs") == ["DVC-4", "DVC-1"]
    assert _keys(lead_api, f"{pid}&blocked=true") == ["DVC-4"]
    assert _keys(lead_api, f"{pid}&blocked=false&type=story") == ["DVC-1"]
    assert _keys(lead_api, f"{pid}&sprintId=none&type=epic") == ["DVC-3"]


def test_assignee_me_and_parent(login_as, lead_api, projects, dataset, people):
    dev_api = login_as(people["dev"])
    assert _keys(dev_api, "assigneeId=me") == ["DVC-1"]
    epic = dataset["epic"]
    child = _issue(lead_api, projects[0], title="Filho", parentIssueId=epic["id"])
    assert _keys(lead_api, f"parentIssueId={epic['id']}") == [child["key"]]


def test_text_search_by_key_and_escaped_title(lead_api, projects, dataset):
    pid = f"projectId={projects[0]['id']}"
    assert _keys(lead_api, f"{pid}&q=dvc-2") == ["DVC-2"]
    assert _keys(lead_api, f"{pid}&q=(sso)") == ["DVC-1"]
    assert _keys(lead_api, f"{pid}&q=.*") == []
    assert _keys(lead_api, f"{pid}&q=LOGIN") == ["DVC-1"]


def test_search_without_project_respects_access(login_as, lead_api, dataset, people):
    assert _keys(login_as(people["other"]), "q=login") == ["OTR-1"]
    assert sorted(_keys(lead_api, "q=login")) == ["DVC-1", "OTR-1"]
    assert sorted(_keys(login_as(people["admin"]), "q=login")) == ["DVC-1", "OTR-1"]
    outsider = login_as(people["other"])
    assert _keys(outsider, "type=bug") == []


def test_inaccessible_or_invalid_project_is_404(login_as, projects, people):
    other_api = login_as(people["other"])
    assert other_api.get(f"/api/issues?projectId={projects[0]['id']}").status_code == 404
    assert other_api.get("/api/issues?projectId=xyz").status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        "status=closed",
        "priority=urgent",
        "type=feature",
        "assigneeId=nobody",
        "sprintId=abc",
        "parentIssueId=abc",
        "page=0",
        "pageSize=101",
        "pageSize=0",
        "sort=-secret",
        f"q={'x' * 101}",
        "blocked=talvez",
    ],
)
def test_invalid_parameters_are_422(lead_api, projects, query):
    response = lead_api.get(f"/api/issues?projectId={projects[0]['id']}&{query}")
    assert response.status_code == 422, query


def test_pagination_total_and_stable_sort(lead_api, projects, dataset):
    pid = f"projectId={projects[0]['id']}"
    first = lead_api.get(f"/api/issues?{pid}&sort=priority&pageSize=2").json()
    second = lead_api.get(f"/api/issues?{pid}&sort=priority&pageSize=2&page=2").json()
    assert first["total"] == second["total"] == 4
    keys = [item["key"] for item in first["items"] + second["items"]]
    assert keys == ["DVC-4", "DVC-3", "DVC-1", "DVC-2"]
    assert _keys(lead_api, f"{pid}&sort=-priority") == ["DVC-2", "DVC-1", "DVC-3", "DVC-4"]
    assert _keys(lead_api, f"{pid}&sort=status")[-1] == "DVC-1"
    assert _keys(lead_api, f"{pid}&sort=title") == ["DVC-4", "DVC-2", "DVC-1", "DVC-3"]
    assert _keys(lead_api, f"{pid}&sort=number") == ["DVC-1", "DVC-2", "DVC-3", "DVC-4"]


def test_list_response_uses_summary_projection(lead_api, projects, dataset):
    item = lead_api.get(f"/api/issues?projectId={projects[0]['id']}").json()["items"][0]
    assert "description" not in item
    assert "acceptanceCriteria" not in item
    assert "dependsOn" not in item
    assert set(SUMMARY_PROJECTION) >= {"key", "labels", "assigneeId"}
    assert "description" not in SUMMARY_PROJECTION


def test_project_labels(login_as, lead_api, projects, dataset, people):
    main = projects[0]
    assert lead_api.get(f"/api/projects/{main['id']}/labels").json() == [
        "auth",
        "billing",
        "docs",
    ]
    assert login_as(people["other"]).get(f"/api/projects/{main['id']}/labels").status_code == 404


def _uses_index(plan: dict[str, Any]) -> bool:
    if plan.get("stage") == "COLLSCAN":
        return False
    children = [plan[name] for name in ("inputStage", "queryPlan") if name in plan]
    children += plan.get("inputStages", [])
    return all(_uses_index(child) for child in children)


@pytest.mark.parametrize(
    ("extra", "sort"),
    [
        ({}, [("number", -1), ("_id", -1)]),
        ({"status": {"$in": ["todo"]}}, [("number", -1), ("_id", -1)]),
        ({}, [("updatedAt", -1), ("_id", -1)]),
        ({}, [("priorityRank", 1), ("_id", 1)]),
        ({"labels": {"$in": ["auth"]}}, [("number", -1), ("_id", -1)]),
        ({"type": {"$in": ["bug"]}}, [("number", -1), ("_id", -1)]),
    ],
)
def test_project_queries_use_indexes(indexed_db: Database, projects, dataset, extra, sort):

    query = {"projectId": ObjectId(projects[0]["id"])} | extra
    explain = indexed_db.issues.find(query).sort(sort).limit(25).explain()
    assert _uses_index(explain["queryPlanner"]["winningPlan"]), explain["queryPlanner"]
