import io
import os
import stat
from urllib.parse import quote

import pytest
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app import cli
from app.domain.attachments import sanitize_filename
from app.domain.permissions import Role
from app.repositories.attachments import AttachmentRepository

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"x" * 64


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


def _upload(api, issue, name="ecrã.png", content=PNG, content_type="image/png"):
    return api.post(
        f"/api/issues/{issue['id']}/attachments",
        files={"file": (name, io.BytesIO(content), content_type)},
    )


def test_upload_list_download_and_delete(apis, issue, api_settings, indexed_db: Database):
    response = _upload(apis["dev"], issue)
    assert response.status_code == 201, response.text
    attachment = response.json()
    assert attachment["originalName"] == "ecrã.png"
    assert attachment["contentType"] == "image/png"
    assert attachment["size"] == len(PNG)
    assert attachment["isImage"] is True and attachment["canDelete"] is True
    assert "storageKey" not in attachment

    document = indexed_db.attachments.find_one()
    project_id, year, month, token = document["storageKey"].split("/")
    assert project_id == issue["projectId"] and len(token) == 32 and "ecr" not in token
    path = api_settings.attachments_path / document["storageKey"]
    assert path.read_bytes() == PNG
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o750

    listing = apis["qa"].get(f"/api/issues/{issue['id']}/attachments").json()
    assert [item["id"] for item in listing] == [attachment["id"]]
    assert listing[0]["canDelete"] is False

    download = apis["qa"].get(f"/api/attachments/{attachment['id']}/content")
    assert download.status_code == 200
    assert download.content == PNG
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-security-policy"] == "sandbox"
    assert download.headers["cache-control"] == "private, no-store"
    disposition = download.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="ecr_.png"')
    assert f"filename*=UTF-8''{quote('ecrã.png')}" in disposition
    inline = apis["qa"].get(f"/api/attachments/{attachment['id']}/content?inline=1")
    assert inline.headers["content-disposition"].startswith("inline;")

    assert apis["qa"].delete(f"/api/attachments/{attachment['id']}").status_code == 403
    assert apis["dev"].delete(f"/api/attachments/{attachment['id']}").status_code == 204
    assert not path.exists()
    assert apis["dev"].get(f"/api/issues/{issue['id']}/attachments").json() == []
    assert apis["dev"].get(f"/api/attachments/{attachment['id']}/content").status_code == 404
    deleted = indexed_db.attachments.find_one({"_id": document["_id"]})
    assert deleted["deletedAt"] is not None and deleted["deletedBy"] is not None


def test_lead_can_delete_and_non_image_is_never_inline(apis, issue):
    attachment = _upload(apis["dev"], issue, "relatório.pdf", PDF, "application/pdf").json()
    response = apis["dev"].get(f"/api/attachments/{attachment['id']}/content?inline=1")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert apis["lead"].delete(f"/api/attachments/{attachment['id']}").status_code == 204


@pytest.mark.parametrize(
    ("name", "content", "status"),
    [
        ("script.exe", b"MZ" + b"\x00" * 10, 422),
        ("sem-extensao", b"texto", 422),
        ("falso.png", b"GIF89a" + b"\x00" * 10, 422),
        ("falso.pdf", b"<html>", 422),
        ("binario.txt", b"abc\x00def", 422),
        ("vazio.txt", b"", 422),
        ("documento.docx", b"PK\x03\x04" + b"\x00" * 20, 201),
        ("notas.md", "# Título\n".encode(), 201),
    ],
)
def test_type_validation(apis, issue, name, content, status, api_settings):
    response = _upload(apis["dev"], issue, name, content, "application/octet-stream")
    assert response.status_code == status, response.text
    if status == 422:
        assert response.json()["field"] == "file"
        assert not any(p.is_file() for p in api_settings.attachments_path.rglob("*"))


def test_path_traversal_in_name_is_neutralised(apis, issue, api_settings, indexed_db):
    response = _upload(apis["dev"], issue, "../../etc/passwd.txt", b"root", "text/plain")
    assert response.status_code == 201, response.text
    assert response.json()["originalName"] == "passwd.txt"
    stored = indexed_db.attachments.find_one()["storageKey"]
    assert (api_settings.attachments_path / stored).is_file()
    assert not (api_settings.attachments_path.parent / "etc").exists()


def test_sanitize_filename_truncates_keeping_extension():
    name = sanitize_filename("a" * 300 + ".pdf")
    assert len(name) == 200 and name.endswith(".pdf")
    assert sanitize_filename("C:\\Users\\x\\foto.png") == "foto.png"
    assert sanitize_filename(" . ") == ""
    assert sanitize_filename("re\x07lat\u200bório\n.txt") == "relatório.txt"


def test_size_and_count_limits(apis, issue, api_app, api_settings):
    api_app.state.settings = api_settings.model_copy(
        update={"attachments_max_bytes": 100, "attachments_max_per_issue": 2}
    )
    too_big = _upload(apis["dev"], issue, "grande.txt", b"x" * 101, "text/plain")
    assert too_big.status_code == 413
    assert too_big.json()["field"] == "file"
    assert not any(p.is_file() for p in api_settings.attachments_path.rglob("*"))

    assert _upload(apis["dev"], issue, "a.txt", b"x" * 100, "text/plain").status_code == 201
    assert _upload(apis["dev"], issue, "b.txt", b"y", "text/plain").status_code == 201
    third = _upload(apis["dev"], issue, "c.txt", b"z", "text/plain")
    assert third.status_code == 422
    assert "máximo de 2 anexos" in third.json()["detail"]


def test_access_control(apis, issue, people, indexed_db):
    attachment = _upload(apis["dev"], issue).json()
    assert _upload(apis["outsider"], issue).status_code == 404
    assert apis["outsider"].get(f"/api/issues/{issue['id']}/attachments").status_code == 404
    assert apis["outsider"].get(f"/api/attachments/{attachment['id']}/content").status_code == 404
    assert apis["outsider"].delete(f"/api/attachments/{attachment['id']}").status_code == 404
    assert apis["dev"].get("/api/attachments/invalido/content").status_code == 404
    assert apis["admin"].get(f"/api/attachments/{attachment['id']}/content").status_code == 200


def test_archived_project_rejects_upload(apis, issue, project, indexed_db):
    indexed_db.projects.update_one(
        {"key": "DVC"}, {"$set": {"status": "archived", "archivedAt": "2026-01-01"}}
    )
    assert _upload(apis["dev"], issue).status_code == 422


def test_metadata_failure_removes_file(apis, issue, api_settings, monkeypatch):
    def fail(self, document):
        raise PyMongoError("falha simulada")

    monkeypatch.setattr(AttachmentRepository, "create", fail)
    assert _upload(apis["dev"], issue).status_code == 500
    assert not any(p.is_file() for p in api_settings.attachments_path.rglob("*"))


def test_history_and_audit(apis, issue, indexed_db):
    attachment = _upload(apis["dev"], issue).json()
    apis["dev"].delete(f"/api/attachments/{attachment['id']}")

    history = apis["dev"].get(f"/api/issues/{issue['id']}/history").json()["items"]
    assert [event["type"] for event in history[:2]] == ["attachment_removed", "attachment_added"]
    assert history[1]["details"]["name"] == "ecrã.png"
    actions = [
        log["action"]
        for log in indexed_db.audit_logs.find({"entityType": "attachment"}).sort("createdAt", 1)
    ]
    assert actions == ["attachment.created", "attachment.deleted"]


def test_cli_attachments_check(apis, issue, api_settings, mongo_client, indexed_db):
    attachment = _upload(apis["dev"], issue).json()
    stdout = io.StringIO()
    args = ["attachments-check"]
    assert cli.main(args, settings=api_settings, client=mongo_client, stdout=stdout) == 0
    assert "Sem inconsistências" in stdout.getvalue()

    key = indexed_db.attachments.find_one()["storageKey"]
    orphan = api_settings.attachments_path / key.rsplit("/", 1)[0] / ("f" * 32)
    orphan.write_bytes(b"x")
    (api_settings.attachments_path / key).unlink()
    stdout = io.StringIO()
    assert cli.main(args, settings=api_settings, client=mongo_client, stdout=stdout) == 1
    output = stdout.getvalue()
    assert f"órfão (sem metadados ativos): {key.rsplit('/', 1)[0]}/{'f' * 32}" in output
    assert f"em falta no disco: {key}" in output
    assert attachment["id"]
