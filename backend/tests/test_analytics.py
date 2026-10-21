from datetime import UTC, date, datetime, timedelta
from io import StringIO

import pytest
from bson import ObjectId
from pymongo.database import Database

from app import cli
from app.domain.analytics import aging_bucket, duration_stats, resolve_period
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
        "/api/projects", json={"key": "ANA", "name": "Analytics", "memberIds": members}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _today() -> date:
    return datetime.now(UTC).date()


def _issue(api, project, **overrides):
    body = {"projectId": project["id"], "type": "story", "title": "Funcionalidade"} | overrides
    response = api.post("/api/issues", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _patch(api, issue, **changes):
    response = api.patch(f"/api/issues/{issue['id']}", json={"version": issue["version"]} | changes)
    assert response.status_code == 200, response.text
    return response.json()


def _finish(api, issue):
    for status in ("in_progress", "code_review", "testing", "done"):
        issue = _patch(api, issue, status=status)
    return issue


def _set(db: Database, issue, **fields):
    db["issues"].update_one({"_id": ObjectId(issue["id"])}, {"$set": fields})


def _run(api, project):
    case = api.post(
        "/api/test-cases",
        json={
            "projectId": project["id"],
            "title": "Login",
            "steps": [{"action": "Entrar"}],
            "expectedResult": "Entra",
        },
    ).json()
    for result in ("pass", "fail", "skipped"):
        response = api.post("/api/test-runs", json={"testCaseId": case["id"], "result": result})
        assert response.status_code == 201, response.text


def test_domain_helpers():
    assert [aging_bucket(days) for days in (0, 7, 8, 30, 31, 90, 91, 400)] == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
    ]
    stats = duration_stats([1.0, 2.0, 3.0, 11.0])
    assert (stats.count, stats.average_days, stats.median_days, stats.p85_days) == (
        4,
        4.2,
        2.5,
        7.4,
    )
    assert duration_stats([]).average_days is None

    today = date(2026, 5, 31)
    period = resolve_period(None, None, today)
    assert (period.first, period.last) == (date(2026, 3, 3), today)
    with pytest.raises(ValueError, match="anterior"):
        resolve_period(date(2026, 6, 1), today, today)
    with pytest.raises(ValueError, match="366"):
        resolve_period(date(2025, 1, 1), today, today)


def test_dashboard_overview_kpis_alerts_and_my_work(apis, people, project, indexed_db):
    lead, dev = apis["lead"], apis["dev"]
    dev_id = str(people["dev"].id)
    mine = _issue(lead, project, title="Minha", assigneeId=dev_id, storyPoints=3)
    _patch(lead, mine, status="in_progress")
    blocked = _issue(lead, project, title="Bloqueada", storyPoints=5)
    blocked = _patch(lead, blocked, blocked=True, blockReason="API")
    _set(indexed_db, blocked, blockedAt=datetime.now(UTC) - timedelta(days=5))
    stale = _issue(lead, project, title="Esquecida")
    _set(indexed_db, stale, updatedAt=datetime.now(UTC) - timedelta(days=20))
    _issue(lead, project, title="Crash", type="bug", priority="critical")
    _finish(lead, _issue(lead, project, title="Feita", storyPoints=2))
    _run(apis["qa"], project)
    other = apis["outsider"].post("/api/projects", json={"key": "OUT", "name": "Alheio"}).json()
    _issue(apis["outsider"], other, title="Alheia")

    response = dev.get("/api/dashboard/overview")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["projectCount"] == 1
    assert body["kpis"] == {
        "openCount": 4,
        "inProgressCount": 1,
        "blockedCount": 1,
        "doneCount": 1,
        "criticalBugCount": 1,
        "openStoryPoints": 8.0,
        "testPassRate": 0.5,
        "testRunCount": 3,
    }
    by_status = {row["status"]: row["issueCount"] for row in body["statusBreakdown"]}
    assert by_status == {"todo": 3, "in_progress": 1, "code_review": 0, "testing": 0, "done": 1}

    alerts = {group["kind"]: group for group in body["alerts"]}
    assert [issue["title"] for issue in alerts["blocked"]["issues"]] == ["Bloqueada"]
    assert alerts["blocked"]["issues"][0]["ageDays"] == 5
    assert [issue["title"] for issue in alerts["stale"]["issues"]] == ["Esquecida"]
    assert alerts["unassigned_critical_bugs"]["total"] == 1

    assert body["myWork"]["openCount"] == 1
    assert body["myWork"]["inProgressCount"] == 1
    assert body["myWork"]["issues"][0]["assignee"]["id"] == dev_id

    outsider = apis["outsider"].get("/api/dashboard/overview").json()
    assert outsider["projectCount"] == 1
    assert outsider["kpis"]["openCount"] == 1


def test_dashboard_project_filter_and_active_sprint(apis, project):
    lead = apis["lead"]
    sprint = lead.post(
        "/api/sprints",
        json={
            "projectId": project["id"],
            "name": "Sprint 1",
            "goal": "Login",
            "startDate": _today().isoformat(),
            "endDate": (_today() + timedelta(days=9)).isoformat(),
        },
    ).json()
    issue = _issue(lead, project, storyPoints=4)
    _issue(lead, project, storyPoints=4)
    response = lead.post(
        f"/api/sprints/{sprint['id']}/issues",
        json={"issueIds": [issue["id"]]},
    )
    assert response.status_code == 200, response.text
    sprint = lead.get(f"/api/sprints/{sprint['id']}").json()
    started = lead.post(f"/api/sprints/{sprint['id']}/start", json={"version": sprint["version"]})
    assert started.status_code == 200, started.text
    _finish(lead, lead.get(f"/api/issues/{issue['id']}").json())

    body = lead.get("/api/dashboard/overview", params={"projectId": project["id"]}).json()
    assert body["projectId"] == project["id"]
    [active] = body["activeSprints"]
    assert active["name"] == "Sprint 1"
    assert active["goal"] == "Login"
    assert active["projectKey"] == "ANA"
    assert active["remainingDays"] == 9
    assert active["progressPercent"] == 100.0

    assert (
        apis["outsider"]
        .get("/api/dashboard/overview", params={"projectId": project["id"]})
        .status_code
        == 404
    )
    assert lead.get("/api/dashboard/overview", params={"projectId": "x"}).status_code == 404


def test_project_metrics(apis, people, project, indexed_db):
    lead = apis["lead"]
    now = datetime.now(UTC)
    done = _finish(lead, _issue(lead, project, title="Feita"))
    _set(indexed_db, done, createdAt=now - timedelta(days=10))
    indexed_db["issue_history"].update_many(
        {"issueId": ObjectId(done["id"]), "changes.to": "in_progress"},
        {"$set": {"createdAt": now - timedelta(days=4)}},
    )
    old = _issue(lead, project, title="Antiga", assigneeId=str(people["dev"].id), storyPoints=3)
    _set(indexed_db, old, createdAt=now - timedelta(days=40))
    _issue(lead, project, title="Bug", type="bug", priority="high")
    _finish(lead, _issue(lead, project, title="Bug feito", type="bug", priority="high"))
    _run(apis["qa"], project)
    release = lead.post(
        "/api/releases",
        json={"projectId": project["id"], "name": "1.0.0", "issueIds": [done["id"]]},
    )
    assert release.status_code == 201, release.text

    response = apis["dev"].get(f"/api/reports/projects/{project['id']}/metrics")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["filters"]["to"] == _today().isoformat()
    assert body["filters"]["from"] == (_today() - timedelta(days=89)).isoformat()
    assert body["kpis"]["openCount"] == 2
    assert body["leadTime"]["count"] == 2
    assert body["leadTime"]["p85Days"] == pytest.approx(8.5, abs=0.1)
    assert body["cycleTime"]["count"] == 2
    assert body["cycleTime"]["averageDays"] == pytest.approx(2.0, abs=0.1)
    assert [bucket["count"] for bucket in body["aging"]["buckets"]] == [1, 0, 1, 0]
    assert body["aging"]["oldest"][0]["title"] == "Antiga"
    high = next(row for row in body["bugSeverity"] if row["priority"] == "high")
    assert (high["open"], high["done"], high["total"]) == (1, 1, 2)
    assert body["qa"]["counts"]["pass"] == 1
    assert body["qa"]["passRate"] == 0.5
    assert body["releases"][0]["name"] == "1.0.0"
    assert body["releases"][0]["doneIssueCount"] == 1
    workload = {
        (row["assignee"] or {}).get("name"): row["openStoryPoints"] for row in body["workload"]
    }
    assert workload == {"Dev": 3.0, None: 0.0}
    assert body["workload"][-1]["assignee"] is None

    bugs = (
        apis["dev"]
        .get(f"/api/reports/projects/{project['id']}/metrics", params={"type": "bug"})
        .json()
    )
    assert bugs["filters"]["type"] == "bug"
    assert bugs["kpis"]["openCount"] == 1
    assert bugs["leadTime"]["count"] == 1


def test_project_metrics_filters_validation_and_access(apis, project):
    lead = apis["lead"]
    url = f"/api/reports/projects/{project['id']}/metrics"
    inverted = lead.get(url, params={"from": "2026-05-10", "to": "2026-05-01"})
    assert inverted.status_code == 422
    assert inverted.json()["field"] == "from"
    too_long = lead.get(url, params={"from": "2024-01-01", "to": "2026-01-01"})
    assert too_long.json()["field"] == "from"
    assert lead.get(url, params={"sprintId": "x"}).json()["field"] == "sprintId"
    assert lead.get(url, params={"sprintId": str(ObjectId())}).json()["field"] == "sprintId"
    assert lead.get(url, params={"type": "nope"}).status_code == 422
    assert apis["outsider"].get(url).status_code == 404

    sprint = lead.post(
        "/api/sprints",
        json={
            "projectId": project["id"],
            "name": "Sprint 1",
            "startDate": "2026-05-01",
            "endDate": "2026-05-14",
        },
    ).json()
    issue = _issue(lead, project)
    lead.post(f"/api/sprints/{sprint['id']}/issues", json={"issueIds": [issue["id"]]})
    _issue(lead, project)
    body = lead.get(url, params={"sprintId": sprint["id"]}).json()
    assert body["filters"]["sprintId"] == sprint["id"]
    assert body["kpis"]["openCount"] == 1
    assert body["velocity"]["sprints"] == []
    assert body["sprints"] == [{"id": sprint["id"], "name": "Sprint 1", "status": "planned"}]


def test_report_snapshots_and_trend(apis, project, indexed_db, mongo_settings, mongo_client):
    lead = apis["lead"]
    _issue(lead, project, storyPoints=2)
    url = f"/api/reports/projects/{project['id']}/snapshots"
    assert apis["dev"].post(url).status_code == 403
    assert apis["outsider"].post(url).status_code == 404

    response = lead.post(url)
    assert response.status_code == 201, response.text
    assert response.json()["kpis"]["openCount"] == 1
    _issue(lead, project)
    assert lead.post(url).json()["kpis"]["openCount"] == 2
    assert indexed_db["report_snapshots"].count_documents({}) == 1

    indexed_db["report_snapshots"].insert_one(
        {
            "projectId": ObjectId(project["id"]),
            "day": datetime.combine(_today() - timedelta(days=1), datetime.min.time(), UTC),
            "kpis": {"openCount": 1, "openStoryPoints": 2},
            "statusBreakdown": [],
            "takenAt": datetime.now(UTC),
        }
    )
    metrics = lead.get(f"/api/reports/projects/{project['id']}/metrics").json()
    assert [point["openCount"] for point in metrics["trend"]] == [1, 2]
    overview = lead.get("/api/dashboard/overview").json()
    assert [point["openCount"] for point in overview["trend"]] == [1, 2]

    archived = lead.post("/api/projects", json={"key": "ARC", "name": "Arquivado"}).json()
    response = lead.post(
        f"/api/projects/{archived['id']}/archive", json={"version": archived["version"]}
    )
    assert response.status_code == 200, response.text
    assert lead.post(f"/api/reports/projects/{archived['id']}/snapshots").status_code == 422

    indexed_db["report_snapshots"].delete_many({})
    stdout = StringIO()
    code = cli.main(
        ["report-snapshots"],
        settings=mongo_settings,
        client=mongo_client,
        stdout=stdout,
        stderr=StringIO(),
    )
    assert code == 0
    assert "1 gravado(s), 0 com erro" in stdout.getvalue()
    assert indexed_db["report_snapshots"].count_documents({}) == 1
