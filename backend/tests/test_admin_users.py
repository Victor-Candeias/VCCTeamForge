import pytest
from fastapi.testclient import TestClient

from app.domain.permissions import Role

NEW_PASSWORD = "outra-password-segura"


@pytest.fixture
def people(make_user):
    return {
        "admin": make_user("Admin", Role.ADMIN),
        "lead": make_user("Lider", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "old": make_user("Antigo", Role.QA, active=False),
    }


@pytest.fixture
def admin_api(login_as, people):
    return login_as(people["admin"])


def _get(api, user):
    return api.get(f"/api/admin/users/{user.id}").json()


def test_only_users_manage_can_access(login_as, people):
    lead = login_as(people["lead"])
    assert lead.get("/api/admin/users").status_code == 403
    payload = {"email": "x@exemplo.pt", "name": "X", "role": "qa", "password": NEW_PASSWORD}
    assert lead.post("/api/admin/users", json=payload).status_code == 403


def test_list_includes_disabled_users_and_filters(admin_api, people):
    response = admin_api.get("/api/admin/users")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert [user["name"] for user in body["items"]] == ["Admin", "Antigo", "Dev", "Lider"]
    assert "passwordHash" not in body["items"][0]

    disabled = admin_api.get("/api/admin/users", params={"status": "disabled"}).json()
    assert [user["name"] for user in disabled["items"]] == ["Antigo"]
    leads = admin_api.get("/api/admin/users", params={"role": "tech_lead", "q": "lid"}).json()
    assert [user["email"] for user in leads["items"]] == ["lider@exemplo.pt"]


def test_create_user_can_login_and_is_audited(admin_api, api_app, people):
    payload = {"email": "Nova@Exemplo.pt", "name": " Nova ", "role": "qa", "password": NEW_PASSWORD}
    response = admin_api.post("/api/admin/users", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["name"] == "Nova"
    assert created["status"] == "active"
    assert created["version"] == 1

    with TestClient(api_app) as client:
        csrf = client.get("/api/auth/csrf").json()["csrfToken"]
        login = client.post(
            "/api/auth/login",
            json={"email": "nova@exemplo.pt", "password": NEW_PASSWORD},
            headers={"X-CSRF-Token": csrf},
        )
        assert login.status_code == 200

    logs = admin_api.get("/api/audit-logs", params={"action": "user.created"}).json()
    assert logs["items"][0]["actor"]["id"] == str(people["admin"].id)


@pytest.mark.parametrize(
    ("payload", "status", "field"),
    [
        ({"email": "dev@exemplo.pt"}, 409, "email"),
        ({"email": "sem-arroba"}, 422, "email"),
        ({"name": "   "}, 422, "name"),
        ({"password": "curta"}, 422, "password"),
    ],
)
def test_create_user_validation(admin_api, payload, status, field):
    base = {"email": "novo@exemplo.pt", "name": "Novo", "role": "developer"}
    response = admin_api.post(
        "/api/admin/users", json={**base, "password": NEW_PASSWORD, **payload}
    )
    assert response.status_code == status
    assert response.json()["field"] == field


def test_update_user_fields_and_conflicts(admin_api, people):
    dev = _get(admin_api, people["dev"])
    response = admin_api.patch(
        f"/api/admin/users/{dev['id']}",
        json={"version": dev["version"], "name": "Dev Sénior", "role": "tech_lead"},
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert (updated["name"], updated["role"], updated["version"]) == ("Dev Sénior", "tech_lead", 2)

    stale = admin_api.patch(f"/api/admin/users/{dev['id']}", json={"version": 1, "name": "X"})
    assert stale.status_code == 409
    assert stale.json()["currentVersion"] == 2

    duplicate = admin_api.patch(
        f"/api/admin/users/{dev['id']}", json={"version": 2, "email": "LIDER@exemplo.pt"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["field"] == "email"

    logs = admin_api.get("/api/audit-logs", params={"action": "user.updated"}).json()
    changes = logs["items"][0]["details"]["changes"]
    assert changes["role"] == {"from": "developer", "to": "tech_lead"}


def test_admin_cannot_demote_or_disable_self(admin_api, people):
    me = _get(admin_api, people["admin"])
    for change, field in (({"role": "qa"}, "role"), ({"status": "disabled"}, "status")):
        response = admin_api.patch(
            f"/api/admin/users/{me['id']}", json={"version": me["version"], **change}
        )
        assert response.status_code == 422
        assert response.json()["field"] == field
    renamed = admin_api.patch(
        f"/api/admin/users/{me['id']}", json={"version": me["version"], "name": "Chefe"}
    )
    assert renamed.status_code == 200


def test_disable_ends_sessions_and_blocks_login(admin_api, login_as, people):
    dev_api = login_as(people["dev"])
    assert dev_api.get("/api/users/me").status_code == 200
    dev = _get(admin_api, people["dev"])

    response = admin_api.patch(
        f"/api/admin/users/{dev['id']}", json={"version": dev["version"], "status": "disabled"}
    )
    assert response.status_code == 200
    assert dev_api.get("/api/users/me").status_code == 401
    with pytest.raises(AssertionError):
        login_as(people["dev"])

    reactivated = admin_api.patch(
        f"/api/admin/users/{dev['id']}", json={"version": dev["version"] + 1, "status": "active"}
    )
    assert reactivated.status_code == 200
    assert login_as(people["dev"]).get("/api/users/me").status_code == 200


def test_reset_password(admin_api, login_as, api_app, people):
    dev_api = login_as(people["dev"])
    dev = _get(admin_api, people["dev"])

    weak = admin_api.post(
        f"/api/admin/users/{dev['id']}/password", json={"version": dev["version"], "password": "x"}
    )
    assert weak.status_code == 422
    assert weak.json()["field"] == "password"

    response = admin_api.post(
        f"/api/admin/users/{dev['id']}/password",
        json={"version": dev["version"], "password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["version"] == dev["version"] + 1
    assert dev_api.get("/api/users/me").status_code == 401

    with TestClient(api_app) as client:
        csrf = client.get("/api/auth/csrf").json()["csrfToken"]
        login = client.post(
            "/api/auth/login",
            json={"email": people["dev"].email, "password": NEW_PASSWORD},
            headers={"X-CSRF-Token": csrf},
        )
        assert login.status_code == 200


def test_reset_own_password_keeps_current_session(admin_api, people):
    me = _get(admin_api, people["admin"])
    response = admin_api.post(
        f"/api/admin/users/{me['id']}/password",
        json={"version": me["version"], "password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert admin_api.get("/api/users/me").status_code == 200


def test_unknown_user_is_404(admin_api):
    assert admin_api.get("/api/admin/users/000000000000000000000000").status_code == 404
    assert admin_api.get("/api/admin/users/invalido").status_code == 404
