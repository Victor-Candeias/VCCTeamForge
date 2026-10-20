import hashlib
import io
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import cache

import pytest
from argon2 import PasswordHasher
from bson import ObjectId
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from pymongo.database import Database

from app import cli
from app.api.deps import require_permissions
from app.core import security
from app.core.config import DEFAULT_DATABASE_DIR, Settings
from app.core.errors import NotFoundError
from app.domain.permissions import Permission, Role, permissions_for
from app.domain.users import User, UserStatus
from app.main import create_app
from app.maintenance import indexes
from app.repositories.users import EmailAlreadyExistsError, UserRepository
from app.services import authorization
from app.services.users import UserService

PASSWORD = "uma-password-segura"
AUTH_COLLECTIONS = {"users", "sessions", "login_attempts"}


@pytest.fixture
def auth_settings(mongo_settings: Settings) -> Settings:
    return mongo_settings.model_copy(
        update={"login_max_failures_per_email": 3, "login_max_failures_per_ip": 10}
    )


@cache
def _password_hash() -> str:
    return security.hash_password(PASSWORD)


@pytest.fixture
def users(db: Database) -> dict[str, User]:
    """Um utilizador por perfil (hash calculado uma vez: o Argon2id é lento de propósito)."""
    specs = indexes.load_index_specs(DEFAULT_DATABASE_DIR)
    indexes.ensure_indexes(db, [spec for spec in specs if spec.collection in AUTH_COLLECTIONS])
    repository = UserRepository(db)
    return {
        role.value: User.from_document(
            repository.create(
                email=f"{role.value}@exemplo.pt",
                name=role.value,
                role=role,
                password_hash=_password_hash(),
                now=datetime.now(UTC),
            )
        )
        for role in Role
    }


@pytest.fixture
def client(auth_settings: Settings, mongo_client, users) -> Iterator[TestClient]:
    app = create_app(auth_settings, mongo_client=mongo_client)
    probe = APIRouter()

    @probe.get("/api/test/users-admin")
    def users_admin(user: User = Depends(require_permissions(Permission.USERS_MANAGE))) -> dict:
        return {"id": str(user.id)}

    app.include_router(probe)
    with TestClient(app) as test_client:
        yield test_client


def _csrf(client: TestClient) -> str:
    return client.get("/api/auth/csrf").json()["csrfToken"]


def _login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": _csrf(client)},
    )


def _post(client: TestClient, path: str):
    return client.post(path, headers={"X-CSRF-Token": client.cookies.get("vcctf_csrf", "")})


def test_login_creates_server_side_session(client: TestClient, db: Database):
    response = _login(client, "  Developer@Exemplo.PT ")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "developer@exemplo.pt"
    assert body["role"] == "developer"
    assert "issues:write" in body["permissions"]
    assert response.headers["cache-control"] == "no-store"
    session_cookie = next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith("vcctf_session=")
    )
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie

    token = client.cookies["vcctf_session"]
    session = db.sessions.find_one()
    assert session["tokenHash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(session)
    assert db.audit_logs.find_one({"action": "auth.login"})["requestId"]

    me = client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


@pytest.mark.parametrize("headers", [{}, {"X-CSRF-Token": "outro"}])
def test_login_requires_csrf_token(client: TestClient, headers: dict):
    _csrf(client)
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@exemplo.pt", "password": PASSWORD},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"


def test_invalid_credentials_are_indistinguishable(client: TestClient, db: Database):
    wrong_password = _login(client, "admin@exemplo.pt", "password-errada!")
    unknown_user = _login(client, "ninguem@exemplo.pt")

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["detail"] == unknown_user.json()["detail"]
    assert "vcctf_session" not in client.cookies
    assert db.audit_logs.count_documents({"action": "auth.login_failed"}) == 2


def test_login_rate_limit_per_email(client: TestClient):
    for _ in range(3):
        assert _login(client, "qa@exemplo.pt", "password-errada!").status_code == 401

    blocked = _login(client, "qa@exemplo.pt")

    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["retry-after"]) <= 15 * 60
    assert _login(client, "admin@exemplo.pt").status_code == 200


def test_successful_login_resets_email_failures(client: TestClient):
    for _ in range(2):
        _login(client, "qa@exemplo.pt", "password-errada!")
    assert _login(client, "qa@exemplo.pt").status_code == 200
    for _ in range(2):
        assert _login(client, "qa@exemplo.pt", "password-errada!").status_code == 401
    assert _login(client, "qa@exemplo.pt").status_code == 200


def test_me_requires_session(client: TestClient):
    response = client.get("/api/users/me")
    assert response.status_code == 401
    assert response.json()["title"] == "Autenticação necessária"


def test_logout_ends_session(client: TestClient, db: Database):
    _login(client, "admin@exemplo.pt")

    assert client.post("/api/auth/logout").status_code == 403
    response = _post(client, "/api/auth/logout")

    assert response.status_code == 204
    assert db.sessions.count_documents({}) == 0
    assert "vcctf_session" not in client.cookies
    assert client.get("/api/users/me").status_code == 401
    assert db.audit_logs.count_documents({"action": "auth.logout"}) == 1


def test_csrf_token_is_bound_to_session(client: TestClient):
    pre_login_token = _csrf(client)
    _login(client, "admin@exemplo.pt")
    client.cookies.set("vcctf_csrf", pre_login_token)

    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": pre_login_token})

    assert response.status_code == 403


def test_expired_session_is_rejected(client: TestClient, db: Database):
    _login(client, "admin@exemplo.pt")
    db.sessions.update_many({}, {"$set": {"expiresAt": datetime.now(UTC) - timedelta(seconds=1)}})

    assert client.get("/api/users/me").status_code == 401


def test_session_idle_expiration_slides_until_absolute_limit(client: TestClient, db: Database):
    _login(client, "admin@exemplo.pt")
    old = datetime.now(UTC) - timedelta(minutes=10)
    db.sessions.update_many(
        {}, {"$set": {"lastSeenAt": old, "expiresAt": old + timedelta(hours=2)}}
    )

    client.get("/api/users/me")

    session = db.sessions.find_one()
    assert session["expiresAt"] > old + timedelta(hours=2)
    assert session["expiresAt"] <= session["absoluteExpiresAt"]


def test_disabled_user_cannot_login_and_loses_session(client: TestClient, db: Database):
    _login(client, "developer@exemplo.pt")
    db.users.update_one(
        {"normalizedEmail": "developer@exemplo.pt"}, {"$set": {"status": UserStatus.DISABLED}}
    )

    assert client.get("/api/users/me").status_code == 401
    assert db.sessions.count_documents({}) == 0
    assert _login(client, "developer@exemplo.pt").status_code == 401
    failed = db.audit_logs.find_one({"action": "auth.login_failed"})
    assert failed["details"]["reason"] == "disabled"


def test_require_permissions(client: TestClient):
    assert client.get("/api/test/users-admin").status_code == 401
    _login(client, "tech_lead@exemplo.pt")
    assert client.get("/api/test/users-admin").status_code == 403
    _login(client, "admin@exemplo.pt")
    assert client.get("/api/test/users-admin").status_code == 200


def test_login_upgrades_outdated_password_hash(client: TestClient, db: Database):
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    db.users.update_one({"normalizedEmail": "qa@exemplo.pt"}, {"$set": {"passwordHash": weak_hash}})

    assert _login(client, "qa@exemplo.pt").status_code == 200

    new_hash = db.users.find_one({"normalizedEmail": "qa@exemplo.pt"})["passwordHash"]
    assert new_hash != weak_hash
    assert not security.password_needs_rehash(new_hash)


def test_role_permissions_follow_readme_profiles():
    assert permissions_for(Role.ADMIN) == frozenset(Permission)
    assert Permission.SPRINTS_MANAGE in permissions_for(Role.TECH_LEAD)
    assert Permission.RELEASES_APPROVE not in permissions_for(Role.DEVELOPER)
    assert Permission.SPRINTS_MANAGE not in permissions_for(Role.DEVELOPER)
    assert {Permission.TESTS_EXECUTE, Permission.ISSUES_WRITE} <= permissions_for(Role.QA)
    assert Permission.USERS_MANAGE not in permissions_for(Role.TECH_LEAD)


def _user(role: Role) -> User:
    return User(ObjectId(), "u@exemplo.pt", "U", role, UserStatus.ACTIVE)


def test_project_access_requires_membership():
    member, lead, outsider = _user(Role.DEVELOPER), _user(Role.TECH_LEAD), _user(Role.QA)
    project = {"_id": ObjectId(), "leadUserId": lead.id, "memberIds": [member.id]}

    assert authorization.can_access_project(member, project)
    assert authorization.can_access_project(lead, project)
    assert authorization.can_access_project(_user(Role.ADMIN), project)
    with pytest.raises(NotFoundError):
        authorization.ensure_project_access(outsider, project)
    with pytest.raises(NotFoundError):
        authorization.ensure_project_access(member, None)
    assert authorization.accessible_projects_filter(_user(Role.ADMIN)) == {}
    assert authorization.accessible_projects_filter(member) == {
        "$or": [{"memberIds": member.id}, {"leadUserId": member.id}]
    }


def test_password_hashing():
    password_hash = security.hash_password(PASSWORD)
    assert password_hash.startswith("$argon2id$")
    assert "m=19456,t=2,p=1" in password_hash
    assert security.verify_password(password_hash, PASSWORD)
    assert not security.verify_password(password_hash, "outra-password")
    assert not security.verify_password("não-é-um-hash", PASSWORD)


@pytest.mark.parametrize(
    ("email", "password", "message"),
    [
        ("invalido", PASSWORD, "Email"),
        ("ok@exemplo.pt", "curta", "12"),
        ("ok@exemplo.pt", "x" * 129, "128"),
    ],
)
def test_create_user_validation(db: Database, email: str, password: str, message: str):
    with pytest.raises(ValueError, match=message):
        UserService(db).create_user(email=email, name="N", role=Role.QA, password=password)


def test_create_user_rejects_duplicate_email(db: Database, users):
    with pytest.raises(EmailAlreadyExistsError):
        UserService(db).create_user(
            email="ADMIN@exemplo.pt", name="Outro", role=Role.ADMIN, password=PASSWORD
        )


def _run_create_user(settings, mongo_client, *extra: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = cli.main(
        ["create-user", "--email", "chefe@exemplo.pt", "--name", "Chefe", *extra],
        settings=settings,
        client=mongo_client,
        stdout=stdout,
        stderr=stderr,
    )
    return code, stdout.getvalue(), stderr.getvalue()


def test_cli_create_user(db: Database, mongo_settings, mongo_client, monkeypatch):
    indexes.ensure_indexes(db, indexes.load_index_specs(DEFAULT_DATABASE_DIR))
    monkeypatch.setenv(cli.PASSWORD_ENV, PASSWORD)

    code, out, _ = _run_create_user(mongo_settings, mongo_client)
    assert code == 0
    assert "chefe@exemplo.pt (admin" in out
    document = db.users.find_one({"normalizedEmail": "chefe@exemplo.pt"})
    assert security.verify_password(document["passwordHash"], PASSWORD)
    assert db.audit_logs.find_one({"action": "user.created"})["details"]["source"] == "cli"

    code, _, err = _run_create_user(mongo_settings, mongo_client, "--role", "qa")
    assert code == 1
    assert "Já existe" in err


def test_cli_create_user_requires_password_source(db, mongo_settings, mongo_client, monkeypatch):
    monkeypatch.delenv(cli.PASSWORD_ENV, raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO())

    code, _, err = _run_create_user(mongo_settings, mongo_client)

    assert code == 1
    assert cli.PASSWORD_ENV in err
