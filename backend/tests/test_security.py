"""Garantias de segurança transversais a todas as rotas da API (DEV-025).

Percorrem as rotas registadas, para que um endpoint novo sem autenticação ou sem CSRF falhe aqui
mesmo que os testes do próprio módulo não o verifiquem.
"""

import re

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.domain.permissions import Role

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/auth/csrf"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
}
_PATH_PARAM = re.compile(r"\{[^}]+\}")


def _api_routes(app) -> list[tuple[str, str]]:
    # Nenhuma rota usa include_in_schema=False: o OpenAPI é o inventário completo.
    return sorted(
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    )


def _concrete(path: str) -> str:
    return _PATH_PARAM.sub(str(ObjectId()), path)


def test_route_inventory_is_not_empty(api_app):
    routes = _api_routes(api_app)
    assert len(routes) > 50
    assert set(routes) >= PUBLIC_ROUTES


def test_every_private_route_requires_a_session(api_app):
    client = TestClient(api_app)
    csrf = client.get("/api/auth/csrf").json()["csrfToken"]
    failures = []
    for method, path in _api_routes(api_app):
        if (method, path) in PUBLIC_ROUTES:
            continue
        # CSRF válido, para que a resposta dependa apenas da falta de sessão.
        response = client.request(method, _concrete(path), headers={"X-CSRF-Token": csrf})
        if response.status_code != 401:
            failures.append(f"{method} {path}: {response.status_code}")
    assert failures == []


@pytest.mark.parametrize("role", [Role.ADMIN, Role.QA])
def test_every_unsafe_route_requires_csrf(make_user, login_as, api_app, role: Role):
    api = login_as(make_user("Seguranca", role))
    failures = []
    for method, path in _api_routes(api_app):
        if method not in UNSAFE_METHODS:
            continue
        for headers in ({}, {"X-CSRF-Token": "forjado"}):
            response = api.client.request(method, _concrete(path), headers=headers)
            if response.status_code != 403:
                failures.append(f"{method} {path} {headers}: {response.status_code}")
    assert failures == []
    assert api.get("/api/users/me").status_code == 200
