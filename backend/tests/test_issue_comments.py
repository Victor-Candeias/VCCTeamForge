import pytest
from pymongo.database import Database

from app.domain.permissions import Role


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "qa": make_user("Qa", Role.QA),
        "outsider": make_user("Outsider", Role.DEVELOPER),
    }


@pytest.fixture
def apis(login_as, people):
    return {name: login_as(user) for name, user in people.items()}


@pytest.fixture
def project(apis, people):
    members = [str(people["dev"].id), str(people["qa"].id)]
    response = apis["lead"].post(
        "/api/projects", json={"key": "DVC", "name": "Projeto", "memberIds": members}
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


def _comment(api, issue, body="Olá **mundo**"):
    return api.post(f"/api/issues/{issue['id']}/comments", json={"body": body})


def test_create_and_list_comments(apis, issue, people):
    first = _comment(apis["dev"], issue, "  Primeiro  ")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["body"] == "Primeiro"
    assert body["author"]["id"] == str(people["dev"].id)
    assert body["canEdit"] is True and body["canDelete"] is True
    assert _comment(apis["qa"], issue, "Segundo").status_code == 201

    page = apis["dev"].get(f"/api/issues/{issue['id']}/comments?pageSize=1").json()
    assert page["total"] == 2
    assert [c["body"] for c in page["items"]] == ["Primeiro"]
    second = apis["dev"].get(f"/api/issues/{issue['id']}/comments?pageSize=1&page=2").json()
    assert second["items"][0]["body"] == "Segundo"
    assert second["items"][0]["canEdit"] is False
    assert second["items"][0]["canDelete"] is False


@pytest.mark.parametrize("body", ["", "   ", "x" * 10_001])
def test_invalid_comment_body(apis, issue, body):
    assert _comment(apis["dev"], issue, body).status_code == 422


def test_comment_access_is_limited_to_project(apis, issue):
    assert _comment(apis["outsider"], issue).status_code == 404
    assert apis["outsider"].get(f"/api/issues/{issue['id']}/comments").status_code == 404
    assert apis["dev"].get("/api/issues/abc/comments").status_code == 404


def test_only_author_edits(apis, issue):
    comment = _comment(apis["dev"], issue).json()
    url = f"/api/issues/{issue['id']}/comments/{comment['id']}"
    assert apis["qa"].patch(url, json={"body": "Outro"}).status_code == 403
    assert apis["lead"].patch(url, json={"body": "Outro"}).status_code == 403
    edited = apis["dev"].patch(url, json={"body": "Editado"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "Editado"
    assert edited.json()["editedAt"] is not None


@pytest.mark.parametrize("remover", ["dev", "lead", "admin"])
def test_author_lead_or_admin_soft_delete(apis, issue, indexed_db: Database, remover):
    comment = _comment(apis["dev"], issue).json()
    url = f"/api/issues/{issue['id']}/comments/{comment['id']}"
    assert apis["qa"].delete(url).status_code == 403
    assert apis[remover].delete(url).status_code == 204

    items = apis["qa"].get(f"/api/issues/{issue['id']}/comments").json()["items"]
    assert items[0]["deleted"] is True
    assert items[0]["body"] is None
    stored = indexed_db.issue_comments.find_one()
    assert "body" not in stored and stored["deletedBy"] is not None
    assert apis[remover].delete(url).status_code == 404
    assert apis["dev"].patch(url, json={"body": "x"}).status_code == 404


def test_comment_on_other_issue_is_404(apis, project, issue):
    other = (
        apis["lead"]
        .post("/api/issues", json={"projectId": project["id"], "type": "task", "title": "Outra"})
        .json()
    )
    comment = _comment(apis["dev"], issue).json()
    url = f"/api/issues/{other['id']}/comments/{comment['id']}"
    assert apis["dev"].patch(url, json={"body": "x"}).status_code == 404


def test_archived_project_blocks_comments(apis, project, issue):
    comment = _comment(apis["dev"], issue).json()
    archived = apis["lead"].post(
        f"/api/projects/{project['id']}/archive", json={"version": project["version"]}
    )
    assert archived.status_code == 200, archived.text
    assert _comment(apis["dev"], issue).status_code == 422
    url = f"/api/issues/{issue['id']}/comments/{comment['id']}"
    assert apis["dev"].patch(url, json={"body": "x"}).status_code == 422
    assert apis["dev"].delete(url).status_code == 422
    listed = apis["dev"].get(f"/api/issues/{issue['id']}/comments").json()["items"]
    assert listed[0]["canEdit"] is False
