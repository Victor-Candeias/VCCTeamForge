import pytest
from bson import ObjectId

from app.core.errors import BusinessRuleError
from app.domain.permissions import Role
from app.domain.projects import can_manage_project, normalize_project_key
from app.domain.users import User, UserStatus
from app.schemas.common import parse_sort


def _user(role: Role) -> User:
    return User(ObjectId(), "x@exemplo.pt", "X", role, UserStatus.ACTIVE)


@pytest.mark.parametrize(("raw", "expected"), [(" dvc ", "DVC"), ("ab12", "AB12"), ("Z9", "Z9")])
def test_normalize_project_key(raw: str, expected: str):
    assert normalize_project_key(raw) == expected


@pytest.mark.parametrize("raw", ["A", "1AB", "AB-1", "ABCDEFGHIJK", "", "Á1"])
def test_normalize_project_key_rejects_invalid(raw: str):
    with pytest.raises(ValueError):
        normalize_project_key(raw)


def test_can_manage_project_requires_lead_or_admin():
    lead, other_lead, developer, admin = (
        _user(Role.TECH_LEAD),
        _user(Role.TECH_LEAD),
        _user(Role.DEVELOPER),
        _user(Role.ADMIN),
    )
    project = {"leadUserId": lead.id, "memberIds": [lead.id, developer.id, other_lead.id]}

    assert can_manage_project(lead, project)
    assert can_manage_project(admin, project)
    assert not can_manage_project(other_lead, project)
    assert not can_manage_project(developer, {**project, "leadUserId": developer.id})


def test_parse_sort():
    allowed = {"name": "name", "updatedAt": "updatedAt"}
    assert parse_sort("-updatedAt", allowed, "name") == [("updatedAt", -1), ("_id", -1)]
    assert parse_sort(None, allowed, "name") == [("name", 1), ("_id", 1)]
    with pytest.raises(BusinessRuleError):
        parse_sort("passwordHash", allowed, "name")
