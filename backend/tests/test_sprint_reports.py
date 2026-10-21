from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from app.domain.permissions import Role
from app.services.sprint_reports import ideal_remaining

TODAY = datetime.now(UTC).date()


def _day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


@pytest.fixture
def people(make_user):
    return {
        "lead": make_user("Lead", Role.TECH_LEAD),
        "dev": make_user("Dev", Role.DEVELOPER),
        "outsider": make_user("Outro", Role.DEVELOPER),
    }


@pytest.fixture
def lead_api(login_as, people):
    return login_as(people["lead"])


@pytest.fixture
def project(lead_api, people):
    response = lead_api.post(
        "/api/projects",
        json={"key": "DVC", "name": "VCCTeamForge", "memberIds": [str(people["dev"].id)]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sprint(api, project, name, start, end):
    body = {
        "projectId": project["id"],
        "name": name,
        "startDate": _day(start),
        "endDate": _day(end),
    }
    response = api.post("/api/sprints", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _issue(api, project, title, **fields):
    body = {"projectId": project["id"], "type": "story", "title": title} | fields
    response = api.post("/api/issues", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _add(api, sprint, *issues):
    response = api.post(
        f"/api/sprints/{sprint['id']}/issues", json={"issueIds": [i["id"] for i in issues]}
    )
    assert response.status_code == 200, response.text


def _patch(api, issue, **fields):
    url = f"/api/issues/{issue['id']}"
    current = api.get(url).json()
    response = api.patch(url, json={"version": current["version"]} | fields)
    assert response.status_code == 200, response.text
    return response.json()


def _finish(api, issue):
    for status in ("in_progress", "code_review", "testing", "done"):
        _patch(api, issue, status=status)


def _transition(api, sprint, action, **body):
    current = api.get(f"/api/sprints/{sprint['id']}").json()
    response = api.post(
        f"/api/sprints/{sprint['id']}/{action}", json={"version": current["version"]} | body
    )
    assert response.status_code == 200, response.text


def _report(api, sprint):
    return api.get(f"/api/reports/sprints/{sprint['id']}")


@pytest.fixture
def active(lead_api, project):
    """Sprint de 10 dias iniciado há 3 dias (no calendário) com 5 + 3 + sem estimativa."""
    sprint = _sprint(lead_api, project, "Sprint 1", -3, 6)
    issues = [
        _issue(lead_api, project, "A", storyPoints=5),
        _issue(lead_api, project, "B", storyPoints=3),
        _issue(lead_api, project, "C"),
    ]
    _add(lead_api, sprint, *issues)
    _transition(lead_api, sprint, "start")
    return sprint, issues


def _daily(db: Database, sprint, day):
    return db.sprint_snapshots.find_one(
        {"sprintId": ObjectId(sprint["id"]), "kind": "daily", "day": day}
    )


def test_ideal_line():
    start, end = TODAY, TODAY + timedelta(days=9)
    assert ideal_remaining(start - timedelta(days=1), start, end, 9) == 9
    assert ideal_remaining(start, start, end, 9) == 9
    assert ideal_remaining(start + timedelta(days=3), start, end, 9) == 6
    assert ideal_remaining(end, start, end, 9) == 0
    assert ideal_remaining(end, end, end, 9) == 0


def test_active_sprint_report(lead_api, project, active, indexed_db: Database):
    sprint, (first, second, third) = active
    assert _daily(indexed_db, sprint, _day(0))["totals"]["storyPoints"] == 8

    _finish(lead_api, first)
    assert _daily(indexed_db, sprint, _day(0))["totals"]["completedStoryPoints"] == 5
    _patch(lead_api, second, blocked=True, blockReason="Aguarda API")
    late = _issue(lead_api, project, "D", storyPoints=2)
    _add(lead_api, sprint, late)
    assert lead_api.delete(f"/api/sprints/{sprint['id']}/issues/{third['id']}").status_code == 200
    assert _daily(indexed_db, sprint, _day(0))["totals"]["issueCount"] == 3

    response = _report(lead_api, sprint)

    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert body["status"] == "active"
    assert body["kpis"] == {
        "committedIssueCount": 3,
        "committedStoryPoints": 8,
        "issueCount": 3,
        "storyPoints": 10,
        "unestimatedCount": 0,
        "completedIssueCount": 1,
        "completedStoryPoints": 5,
        "remainingStoryPoints": 5,
        "progressPercent": 50.0,
        "totalDays": 10,
        "elapsedDays": 4,
        "remainingDays": 6,
        "blockedCount": 1,
        "addedCount": 1,
        "removedCount": 1,
    }
    burndown = body["burndown"]
    assert [point["day"] for point in burndown] == [_day(offset) for offset in range(-3, 7)]
    assert burndown[0]["ideal"] == 8
    assert burndown[-1]["ideal"] == 0
    assert [point["remaining"] for point in burndown[:5]] == [None, None, None, 5, None]
    assert burndown[3]["scope"] == 10
    done = next(item for item in body["statusBreakdown"] if item["status"] == "done")
    assert done == {"status": "done", "issueCount": 1, "storyPoints": 5}
    assert len(body["statusBreakdown"]) == 5
    [blocked] = body["blockedIssues"]
    assert blocked["key"] == second["key"]
    assert blocked["blockReason"] == "Aguarda API"
    assert blocked["blockedAt"] is not None
    assert body["velocity"] == []
    assert body["averageVelocity"] is None


def test_burndown_carries_last_snapshot_forward(lead_api, active, indexed_db: Database):
    sprint, _ = active
    sprint_id = ObjectId(sprint["id"])
    started = datetime.now(UTC) - timedelta(days=3)
    indexed_db.sprints.update_one({"_id": sprint_id}, {"$set": {"startedAt": started}})
    indexed_db.sprint_snapshots.update_many(
        {"sprintId": sprint_id}, {"$set": {"day": _day(-3), "takenAt": started}}
    )
    totals = {"storyPoints": 9, "completedStoryPoints": 3}
    indexed_db.sprint_snapshots.insert_one(
        {
            "sprintId": sprint_id,
            "kind": "daily",
            "day": _day(-2),
            "takenAt": started,
            "totals": totals,
        }
    )

    burndown = _report(lead_api, sprint).json()["burndown"]

    assert [point["remaining"] for point in burndown[:5]] == [8, 6, 6, 8, None]
    assert [point["scope"] for point in burndown[:4]] == [8, 9, 9, 8]
    assert burndown[3]["ideal"] == pytest.approx(5.33)


def test_closed_sprint_report_and_velocity(lead_api, project, active, indexed_db: Database):
    sprint, (first, *_) = active
    _finish(lead_api, first)
    _transition(lead_api, sprint, "close")

    body = _report(lead_api, sprint).json()

    assert body["status"] == "closed"
    assert body["kpis"]["issueCount"] == 3
    assert body["kpis"]["remainingStoryPoints"] == 3
    assert body["kpis"]["removedCount"] == 0
    assert body["burndown"][3]["remaining"] == 3
    assert body["burndown"][4]["remaining"] is None
    assert body["velocity"] == [
        {
            "sprintId": sprint["id"],
            "name": "Sprint 1",
            "committedStoryPoints": 8,
            "completedStoryPoints": 5,
            "committedCompletedStoryPoints": 5,
            "predictabilityPercent": 62.5,
        }
    ]
    assert body["averageVelocity"] == 5
    closing = indexed_db.sprint_snapshots.find_one(
        {"sprintId": ObjectId(sprint["id"]), "kind": "closing"}
    )
    assert _daily(indexed_db, sprint, _day(0))["totals"] == closing["totals"]

    following = _sprint(lead_api, project, "Sprint 2", 7, 16)
    _add(lead_api, following, _issue(lead_api, project, "E", storyPoints=1))
    planned = _report(lead_api, following)
    assert planned.status_code == 422
    assert planned.json()["field"] == "status"


def test_report_access(login_as, people, active):
    sprint, _ = active
    assert _report(login_as(people["dev"]), sprint).status_code == 200
    assert _report(login_as(people["outsider"]), sprint).status_code == 404
    assert login_as(people["dev"]).get(f"/api/reports/sprints/{ObjectId()}").status_code == 404


def test_daily_snapshot_failure_does_not_break_updates(
    lead_api, active, indexed_db: Database, monkeypatch
):
    sprint, (first, *_) = active

    def fail(self, document):
        raise ConnectionFailure("falha simulada")

    monkeypatch.setattr("app.repositories.sprint_snapshots.SprintSnapshotRepository.save", fail)

    updated = _patch(lead_api, first, status="in_progress")

    assert updated["status"] == "in_progress"
    assert _daily(indexed_db, sprint, _day(0))["totals"]["completedStoryPoints"] == 0
