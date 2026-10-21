"""Teste de fumo do script de carga contra um Uvicorn real (porta efémera, BD de teste)."""

import socket
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
import uvicorn
from conftest import API_PASSWORD

from app.domain.permissions import Role
from tools import loadtest


@pytest.fixture
def server_url(api_app):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(api_app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("Uvicorn não arrancou")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_load_test_runs_every_operation(make_user, login_as, server_url, monkeypatch):
    lead = make_user("Carga", Role.TECH_LEAD)
    api = login_as(lead)
    project = api.post("/api/projects", json={"key": "CARGA", "name": "Carga"}).json()
    today = datetime.now(UTC).date()

    def sprint(name: str, offset: int) -> dict:
        body = {
            "projectId": project["id"],
            "name": name,
            "startDate": (today + timedelta(days=offset)).isoformat(),
            "endDate": (today + timedelta(days=offset + 9)).isoformat(),
        }
        response = api.post("/api/sprints", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    active = sprint("Ativa", 0)
    sprint("Planeada", 10)
    issue = api.post(
        "/api/issues", json={"projectId": project["id"], "type": "story", "title": "Base"}
    ).json()
    api.post(f"/api/sprints/{active['id']}/issues", json={"issueIds": [issue["id"]]})
    version = api.get(f"/api/sprints/{active['id']}").json()["version"]
    started = api.post(f"/api/sprints/{active['id']}/start", json={"version": version})
    assert started.status_code == 200, started.text
    monkeypatch.setenv(loadtest.PASSWORD_ENV, API_PASSWORD)
    lines: list[str] = []

    code = loadtest.main(
        [
            "--url",
            server_url,
            "--email",
            lead.email,
            "--project",
            "carga",
            "--users",
            "3",
            "--duration",
            "3",
            "--ramp-up",
            "0.2",
            "--think-time",
            "0",
            "--seed-issues",
            "3",
            "--write",
            "--max-p95-ms",
            "5000",
            "--max-error-rate",
            "0",
        ],
        out=lines.append,
    )

    output = "\n".join(lines)
    assert code == 0, output
    assert "RESULTADO: OK" in output
    for name, _, _ in loadtest.operations(write=True):
        assert f"\n{name} " in output, name
    assert api.get("/api/issues", params={"projectId": project["id"]}).json()["total"] == 4
