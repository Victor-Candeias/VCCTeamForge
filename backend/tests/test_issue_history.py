import logging

import pytest
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.domain.permissions import Role
from app.repositories.issue_history import IssueHistoryRepository
from app.services.issue_history import diff_issue


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
    }


@pytest.fixture
def apis(login_as, people):
    return {name: login_as(user) for name, user in people.items()}


@pytest.fixture
def project(apis, people):
    response = apis["lead"].post(
        "/api/projects",
        json={"key": "DVC", "name": "Projeto", "memberIds": [str(people["dev"].id)]},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def issue(apis, project):
    response = apis["lead"].post(
        "/api/issues", json={"projectId": project["id"], "type": "story", "title": "Story"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _history(api, issue, query=""):
    response = api.get(f"/api/issues/{issue['id']}/history{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_diff_issue_only_reports_changes():
    before = {"title": "A", "status": "todo", "description": "x", "labels": ["a"]}
    changes = {"title": "A", "status": "done", "description": "y", "labels": ["a"]}
    fields = ("title", "status", "description", "labels")
    assert diff_issue(before, changes, fields) == [
        {"field": "status", "from": "todo", "to": "done"},
        {"field": "description", "from": None, "to": None},
    ]


def test_created_and_updated_events(apis, issue, people):
    response = apis["lead"].patch(
        f"/api/issues/{issue['id']}",
        json={
            "version": issue["version"],
            "status": "in_progress",
            "description": "Segredo longo",
            "assigneeId": str(people["dev"].id),
        },
    )
    assert response.status_code == 200, response.text

    history = _history(apis["dev"], issue)
    assert history["total"] == 2
    updated, created = history["items"]
    assert created["type"] == "created"
    assert created["actor"]["id"] == str(people["lead"].id)
    assert updated["type"] == "updated"
    changes = {change["field"]: change for change in updated["changes"]}
    assert changes["status"] == {"field": "status", "from": "todo", "to": "in_progress"}
    assert changes["assigneeId"]["to"] == str(people["dev"].id)
    assert changes["description"] == {"field": "description", "from": None, "to": None}


def test_no_event_when_nothing_changes(apis, issue):
    response = apis["lead"].patch(
        f"/api/issues/{issue['id']}", json={"version": issue["version"], "title": "Story"}
    )
    assert response.status_code == 200
    assert response.json()["version"] == issue["version"]
    assert _history(apis["lead"], issue)["total"] == 1


def test_comment_events_and_pagination(apis, issue):
    comment = apis["dev"].post(f"/api/issues/{issue['id']}/comments", json={"body": "Oi"}).json()
    url = f"/api/issues/{issue['id']}/comments/{comment['id']}"
    apis["dev"].patch(url, json={"body": "Olá"})
    apis["dev"].delete(url)

    types = [event["type"] for event in _history(apis["lead"], issue)["items"]]
    assert types == ["comment_deleted", "comment_edited", "comment_added", "created"]
    first_page = _history(apis["lead"], issue, "?pageSize=2")
    assert [e["type"] for e in first_page["items"]] == ["comment_deleted", "comment_edited"]
    assert first_page["total"] == 4


def test_history_requires_project_access(login_as, make_user, issue):
    outsider = login_as(make_user("Fora", Role.DEVELOPER))
    assert outsider.get(f"/api/issues/{issue['id']}/history").status_code == 404


def test_mutations_are_audited(apis, issue, indexed_db: Database):
    apis["lead"].patch(
        f"/api/issues/{issue['id']}", json={"version": issue["version"], "priority": "high"}
    )
    comment = apis["dev"].post(f"/api/issues/{issue['id']}/comments", json={"body": "Oi"}).json()
    apis["dev"].patch(f"/api/issues/{issue['id']}/comments/{comment['id']}", json={"body": "x"})
    apis["dev"].delete(f"/api/issues/{issue['id']}/comments/{comment['id']}")

    logs = {log["action"]: log for log in indexed_db.audit_logs.find()}
    for action in (
        "issue.created",
        "issue.updated",
        "comment.created",
        "comment.updated",
        "comment.deleted",
    ):
        assert action in logs, action
    assert logs["issue.updated"]["entityType"] == "issue"
    assert logs["issue.updated"]["details"]["changes"][0]["field"] == "priority"
    assert logs["comment.deleted"]["entityType"] == "comment"
    assert logs["comment.deleted"]["details"]["issueKey"] == issue["key"]


def test_history_failure_does_not_break_mutation(apis, issue, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise PyMongoError("indisponível")

    monkeypatch.setattr(IssueHistoryRepository, "record", fail)
    with caplog.at_level(logging.ERROR):
        response = apis["lead"].patch(
            f"/api/issues/{issue['id']}", json={"version": issue["version"], "title": "Novo"}
        )
    assert response.status_code == 200
    assert response.json()["title"] == "Novo"
    assert "Falha ao gravar histórico" in caplog.text


def test_audit_log_endpoint_admin_only_with_filters(apis, issue, people):
    assert apis["lead"].get("/api/audit-logs").status_code == 403
    assert apis["dev"].get("/api/audit-logs").status_code == 403

    page = apis["admin"].get("/api/audit-logs?entityType=issue").json()
    assert page["total"] == 1
    entry = page["items"][0]
    assert entry["action"] == "issue.created"
    assert entry["entityId"] == issue["id"]
    assert entry["actor"]["id"] == str(people["lead"].id)

    by_entity = apis["admin"].get(f"/api/audit-logs?entityId={issue['id']}").json()
    assert [item["action"] for item in by_entity["items"]] == ["issue.created"]
    by_actor = apis["admin"].get(f"/api/audit-logs?actorId={people['lead'].id}").json()
    assert {item["action"] for item in by_actor["items"]} >= {"project.created", "issue.created"}
    actions = apis["admin"].get("/api/audit-logs?action=project.created").json()
    assert actions["total"] == 1
    newest_first = apis["admin"].get("/api/audit-logs").json()["items"]
    stamps = [item["createdAt"] for item in newest_first]
    assert stamps == sorted(stamps, reverse=True)
    assert apis["admin"].get("/api/audit-logs?from=2000-01-01&to=2000-01-02").json()["total"] == 0


@pytest.mark.parametrize("query", ["actorId=abc", "from=ontem", "from=2026-02-01&to=2026-01-01"])
def test_audit_log_invalid_filters(apis, query):
    assert apis["admin"].get(f"/api/audit-logs?{query}").status_code == 422
