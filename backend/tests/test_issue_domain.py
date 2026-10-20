import pytest
from bson import ObjectId

from app.domain.issues import (
    STATUS_RANK,
    IssueRuleError,
    IssueStatus,
    IssueType,
    allowed_transitions,
    can_create_issue_type,
    can_edit_issue,
    normalize_labels,
    validate_parent,
    validate_story_points,
    validate_transition,
)
from app.domain.permissions import Role
from app.domain.users import User, UserStatus


def _user(role: Role) -> User:
    return User(ObjectId(), "x@exemplo.pt", "X", role, UserStatus.ACTIVE)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("todo", "in_progress"),
        ("in_progress", "todo"),
        ("in_progress", "done"),
        ("code_review", "testing"),
        ("testing", "code_review"),
        ("done", "in_progress"),
        ("todo", "todo"),
    ],
)
def test_valid_transitions(current, target):
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [("todo", "done"), ("todo", "code_review"), ("done", "todo"), ("code_review", "todo")],
)
def test_invalid_transitions(current, target):
    with pytest.raises(IssueRuleError) as error:
        validate_transition(current, target)
    assert error.value.field == "status"


def test_allowed_transitions_follow_workflow_order():
    assert allowed_transitions("in_progress") == [
        IssueStatus.TODO,
        IssueStatus.CODE_REVIEW,
        IssueStatus.TESTING,
        IssueStatus.DONE,
    ]
    assert STATUS_RANK[IssueStatus.TODO] == 1
    assert STATUS_RANK[IssueStatus.DONE] == 5


def test_normalize_labels():
    assert normalize_labels([" Backend ", "backend", "API"]) == ["backend", "api"]
    with pytest.raises(IssueRuleError):
        normalize_labels(["  "])
    with pytest.raises(IssueRuleError):
        normalize_labels(["x" * 41])
    with pytest.raises(IssueRuleError):
        normalize_labels([f"l{i}" for i in range(21)])


def test_story_points():
    assert validate_story_points(2.5) == 2.5
    assert validate_story_points(None) is None
    for invalid in (0.3, -1, 101):
        with pytest.raises(IssueRuleError):
            validate_story_points(invalid)


@pytest.mark.parametrize(
    ("issue_type", "parent_type", "valid"),
    [
        ("epic", None, True),
        ("epic", "epic", False),
        ("story", None, True),
        ("story", "epic", True),
        ("story", "task", False),
        ("subtask", None, False),
        ("subtask", "story", True),
        ("subtask", "epic", False),
        ("subtask", "subtask", False),
    ],
)
def test_validate_parent(issue_type, parent_type, valid):
    if valid:
        validate_parent(issue_type, parent_type)
    else:
        with pytest.raises(IssueRuleError):
            validate_parent(issue_type, parent_type)


def test_creation_and_edit_rules_by_role():
    qa, dev, lead = _user(Role.QA), _user(Role.DEVELOPER), _user(Role.TECH_LEAD)
    assert can_create_issue_type(qa, IssueType.BUG)
    assert not can_create_issue_type(qa, IssueType.STORY)
    assert can_create_issue_type(dev, IssueType.STORY)

    other = {"assigneeId": ObjectId(), "reporterId": ObjectId()}
    assert can_edit_issue(lead, other)
    assert not can_edit_issue(dev, other)
    assert can_edit_issue(dev, {**other, "assigneeId": dev.id})
    assert can_edit_issue(qa, {**other, "reporterId": qa.id})
