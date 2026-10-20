"""Releases, checklists e critérios de aprovação (DEV-022)."""

import re
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.common import Priority
from app.domain.issues import IssueStatus, IssueType
from app.domain.permissions import Permission
from app.domain.projects import is_archived
from app.domain.qa import TestRunResult, pass_rate
from app.domain.releases import (
    CRITERIA_LABELS,
    DEFAULT_CRITERIA,
    DEFAULT_RELEASE_CHECKLIST,
    EDITABLE_STATUSES,
    RELEASE_NAME_PATTERN,
    TRANSITIONS,
    ReleaseCriterion,
    ReleaseStatus,
    can_transition,
    release_name_key,
)
from app.domain.users import User
from app.repositories.qa import TestPlanRepository
from app.repositories.releases import ReleaseNameExistsError, ReleaseRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserSummary
from app.schemas.common import PageParams
from app.schemas.releases import (
    ChecklistItem,
    ChecklistItemInput,
    CriterionResult,
    ReleaseBugQuality,
    ReleaseCreate,
    ReleaseCriteria,
    ReleaseHistoryEntry,
    ReleaseIssueQuality,
    ReleaseQuality,
    ReleaseResponse,
    ReleaseSummary,
    ReleaseTestQuality,
    ReleaseTransition,
    ReleaseUpdate,
    TestPlanRef,
)
from app.services.common import date_to_datetime
from app.services.qa import _QaService
from app.services.test_runs import TestRunService

RELEASE_SORT_FIELDS = {"createdAt": "createdAt", "name": "nameKey", "plannedDate": "plannedDate"}
DEFAULT_RELEASE_SORT = "-createdAt"

_TRACKED = ("name", "plannedDate", "issueIds", "knownBugIds", "testPlanIds", "criteria")
_TEXT = ("description", "notes", "checklist")
_APPROVED_RESULTS = (TestRunResult.PASS, TestRunResult.SKIPPED)


class ReleaseService(_QaService):
    entity_label = "Release"

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.releases = ReleaseRepository(db)
        self.plans = TestPlanRepository(db)
        self.users = UserRepository(db)
        self.test_runs = TestRunService(db)

    # Leitura -------------------------------------------------------------------------------

    def search(
        self,
        user: User,
        project_id: ObjectId,
        *,
        statuses: list[ReleaseStatus],
        text: str | None,
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[ReleaseSummary], int]:
        self._get_project(user, project_id)
        query: dict[str, Any] = {"projectId": project_id}
        if statuses:
            query["status"] = {"$in": [status.value for status in statuses]}
        if text:
            query["name"] = {"$regex": re.escape(text), "$options": "i"}
        documents = self.releases.search(
            query, sort=[*sort, ("_id", -1)], skip=page.skip, limit=page.page_size
        )
        return [_summary(document) for document in documents], self.releases.count(query)

    def get(self, user: User, release_id: ObjectId) -> ReleaseResponse:
        release, project = self._get_release(user, release_id)
        return self._response(user, project, release)

    # Escrita -------------------------------------------------------------------------------

    def create(self, user: User, data: ReleaseCreate) -> ReleaseResponse:
        project = self._project_for_write(user, data.project_id)
        name = _release_name(data.name)
        now = datetime.now(UTC)
        if data.checklist is None:
            checklist = self._inherited_checklist(project["_id"])
        else:
            checklist = _checklist(data.checklist, [], user, now)
        release: dict[str, Any] = {
            "projectId": project["_id"],
            "name": name,
            "nameKey": release_name_key(name),
            "description": data.description.strip(),
            "notes": data.notes.strip(),
            "status": ReleaseStatus.DRAFT.value,
            "plannedDate": date_to_datetime(data.planned_date),
            "releasedAt": None,
            "issueIds": self._resolve_issues(project["_id"], data.issue_ids, "issueIds"),
            "knownBugIds": self._resolve_issues(
                project["_id"], data.known_bug_ids, "knownBugIds", bugs_only=True
            ),
            "testPlanIds": self._resolve_test_plans(project["_id"], data.test_plan_ids),
            "checklist": checklist,
            "criteria": data.criteria.model_dump(by_alias=True),
            "history": [_history("created", user, now)],
            "createdBy": user.id,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        try:
            release = self.releases.create(release)
        except ReleaseNameExistsError as error:
            raise _duplicate_name(name) from error
        self._audit("release.created", "release", user, project, release, now, {"name": name})
        return self._response(user, project, release)

    def update(self, user: User, release_id: ObjectId, data: ReleaseUpdate) -> ReleaseResponse:
        release, project = self._get_release(user, release_id)
        self._ensure_writable_project(project)
        if ReleaseStatus(release["status"]) not in EDITABLE_STATUSES:
            raise BusinessRuleError(
                "Só é possível alterar releases em rascunho ou prontas para QA", field="status"
            )
        provided = data.model_fields_set - {"version"}
        now = datetime.now(UTC)
        changes: dict[str, Any] = {}
        if "name" in provided:
            if data.name is None:
                raise BusinessRuleError("Campo obrigatório", field="name")
            changes["name"] = _release_name(data.name)
            changes["nameKey"] = release_name_key(changes["name"])
        if "description" in provided:
            changes["description"] = (data.description or "").strip()
        if "notes" in provided:
            changes["notes"] = (data.notes or "").strip()
        if "planned_date" in provided:
            changes["plannedDate"] = date_to_datetime(data.planned_date)
        if "issue_ids" in provided:
            changes["issueIds"] = self._resolve_issues(
                project["_id"], data.issue_ids or [], "issueIds"
            )
        if "known_bug_ids" in provided:
            changes["knownBugIds"] = self._resolve_issues(
                project["_id"], data.known_bug_ids or [], "knownBugIds", bugs_only=True
            )
        if "test_plan_ids" in provided:
            changes["testPlanIds"] = self._resolve_test_plans(
                project["_id"], data.test_plan_ids or []
            )
        if "checklist" in provided:
            changes["checklist"] = _checklist(
                data.checklist or [], release.get("checklist", []), user, now
            )
        if "criteria" in provided:
            criteria = data.criteria or ReleaseCriteria()
            changes["criteria"] = criteria.model_dump(by_alias=True)

        diff = self._diff(release, changes, _TRACKED, _TEXT)
        if "nameKey" in changes and "name" not in diff:
            changes.pop("name")
            changes.pop("nameKey")
        if not diff:
            if release.get("version", 1) != data.version:
                raise self._conflict(release.get("version", 1))
            return self._response(user, project, release)

        entry = _history("updated", user, now, fields=list(diff))
        try:
            updated = self.releases.update_versioned(
                release_id, data.version, now=now, set_fields=changes, history=entry
            )
        except ReleaseNameExistsError as error:
            raise _duplicate_name(changes["name"]) from error
        updated = self._require_updated(updated, self.releases.find_by_id(release_id))
        self._audit("release.updated", "release", user, project, updated, now, {"changes": diff})
        return self._response(user, project, updated)

    def transition(
        self, user: User, release_id: ObjectId, data: ReleaseTransition
    ) -> ReleaseResponse:
        release, project = self._get_release(user, release_id)
        self._ensure_writable_project(project)
        current = ReleaseStatus(release["status"])
        transition = TRANSITIONS.get((current, data.to))
        if transition is None:
            raise BusinessRuleError(
                f"Transição inválida de {current.value} para {data.to.value}", field="to"
            )
        if not can_transition(user, transition):
            raise ForbiddenError("Não tem permissão para esta transição")
        comment = data.comment.strip()
        if transition.comment_required and not comment:
            raise BusinessRuleError("Indique o motivo", field="comment")
        if release.get("version", 1) != data.version:
            raise self._conflict(release.get("version", 1))
        if data.to is ReleaseStatus.APPROVED:
            self._ensure_approvable(release)

        now = datetime.now(UTC)
        changes: dict[str, Any] = {"status": data.to.value}
        if data.to is ReleaseStatus.RELEASED:
            changes["releasedAt"] = now
        entry = _history(
            transition.action, user, now, from_status=current, to_status=data.to, comment=comment
        )
        updated = self.releases.update_versioned(
            release_id, data.version, now=now, set_fields=changes, history=entry
        )
        updated = self._require_updated(updated, self.releases.find_by_id(release_id))
        details: dict[str, Any] = {"from": current.value, "to": data.to.value}
        if comment:
            details["comment"] = comment
        self._audit("release.transitioned", "release", user, project, updated, now, details)
        return self._response(user, project, updated)

    # Validação -----------------------------------------------------------------------------

    def _ensure_approvable(self, release: dict[str, Any]) -> None:
        pending = [
            item["label"]
            for item in release.get("checklist", [])
            if item.get("required") and not item.get("done")
        ]
        if pending:
            raise BusinessRuleError(
                "Itens obrigatórios da checklist por concluir: " + ", ".join(pending),
                field="checklist",
            )
        failed = [
            criterion.label
            for criterion in self._quality(release).criteria
            if criterion.enabled and not criterion.passed
        ]
        if failed:
            raise BusinessRuleError(
                "Critérios de aprovação não cumpridos: " + ", ".join(failed), field="criteria"
            )

    def _resolve_issues(
        self,
        project_id: ObjectId,
        values: Iterable[str],
        field: str,
        *,
        bugs_only: bool = False,
    ) -> list[ObjectId]:
        issue_ids = self._object_ids(values, field)
        found = self.issues.find_many_by_ids(issue_ids)
        for issue_id in issue_ids:
            issue = found.get(issue_id)
            if issue is None or issue["projectId"] != project_id:
                raise BusinessRuleError(
                    "As issues indicadas têm de existir e pertencer ao projeto", field=field
                )
            if bugs_only and issue["type"] != IssueType.BUG.value:
                raise BusinessRuleError(
                    "Os bugs conhecidos têm de ser issues do tipo bug", field=field
                )
        return issue_ids

    def _resolve_test_plans(self, project_id: ObjectId, values: Iterable[str]) -> list[ObjectId]:
        plan_ids = self._object_ids(values, "testPlanIds")
        found = self.plans.find_many_by_ids(plan_ids)
        for plan_id in plan_ids:
            plan = found.get(plan_id)
            if plan is None or plan["projectId"] != project_id:
                raise BusinessRuleError(
                    "Os planos de teste têm de existir e pertencer ao projeto",
                    field="testPlanIds",
                )
        return plan_ids

    def _inherited_checklist(self, project_id: ObjectId) -> list[dict[str, Any]]:
        """Itens da release mais recente do projeto (por marcar) ou a checklist por omissão."""
        previous = self.releases.latest_for_project(project_id)
        template = (
            [(item["label"], bool(item.get("required"))) for item in previous["checklist"]]
            if previous and previous.get("checklist")
            else list(DEFAULT_RELEASE_CHECKLIST)
        )
        return [_new_item(label, required) for label, required in template]

    # Qualidade -----------------------------------------------------------------------------

    def _quality(self, release: dict[str, Any]) -> ReleaseQuality:
        issues = self.issues.find_many_by_ids(release.get("issueIds", []))
        bugs = self.issues.find_many_by_ids(release.get("knownBugIds", []))
        done = sum(1 for issue in issues.values() if issue["status"] == IssueStatus.DONE.value)
        open_bugs = [bug for bug in bugs.values() if bug["status"] != IssueStatus.DONE.value]
        critical_open = {
            issue["_id"]
            for issue in [*issues.values(), *bugs.values()]
            if issue["type"] == IssueType.BUG.value
            and issue["priority"] == Priority.CRITICAL.value
            and issue["status"] != IssueStatus.DONE.value
        }

        plans = self.plans.find_many_by_ids(release.get("testPlanIds", []))
        counts = {result: 0 for result in TestRunResult}
        total_cases = executed = regressions = 0
        for plan in plans.values():
            progress = self.test_runs.progress_for(plan)
            total_cases += progress.total_cases
            executed += progress.executed_cases
            regressions += progress.regressions
            for result, count in progress.counts.items():
                counts[result] += count
        approved_cases = sum(counts[result] for result in _APPROVED_RESULTS)

        enabled = {**DEFAULT_CRITERIA, **release.get("criteria", {})}
        checks = {
            ReleaseCriterion.ISSUES_DONE: (
                done == len(issues),
                f"{done}/{len(issues)} issues concluídas",
            ),
            ReleaseCriterion.TESTS_PASSED: (
                bool(plans) and total_cases > 0 and approved_cases == total_cases,
                f"{approved_cases}/{total_cases} casos aprovados"
                if plans
                else "Sem planos de teste associados",
            ),
            ReleaseCriterion.NO_OPEN_CRITICAL_BUGS: (
                not critical_open,
                f"{len(critical_open)} bugs críticos em aberto",
            ),
        }
        criteria = [
            CriterionResult(
                key=criterion,
                label=CRITERIA_LABELS[criterion],
                enabled=bool(enabled.get(criterion.value)),
                passed=passed,
                detail=detail,
            )
            for criterion, (passed, detail) in checks.items()
        ]
        checklist_ready = all(
            item.get("done") or not item.get("required") for item in release.get("checklist", [])
        )
        return ReleaseQuality(
            issues=ReleaseIssueQuality(total=len(issues), done=done),
            known_bugs=ReleaseBugQuality(
                total=len(bugs),
                open=len(open_bugs),
                open_critical=sum(1 for bug in open_bugs if bug["_id"] in critical_open),
            ),
            tests=ReleaseTestQuality(
                plans=len(plans),
                total_cases=total_cases,
                executed_cases=executed,
                counts=counts,
                pass_rate=pass_rate({result.value: count for result, count in counts.items()}),
                regressions=regressions,
            ),
            criteria=criteria,
            ready=checklist_ready and all(item.passed for item in criteria if item.enabled),
        )

    # Respostas -----------------------------------------------------------------------------

    def _get_release(
        self, user: User, release_id: ObjectId
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        release = self.releases.find_by_id(release_id)
        if release is None:
            raise NotFoundError("Release não encontrada")
        try:
            project = self._get_project(user, release["projectId"])
        except NotFoundError as error:
            raise NotFoundError("Release não encontrada") from error
        return release, project

    def _conflict(self, current_version: int) -> ConflictError:
        return ConflictError(
            "A release foi alterada entretanto. Recarregue e tente novamente.",
            currentVersion=current_version,
        )

    def _require_updated(
        self, updated: dict[str, Any] | None, current: dict[str, Any] | None
    ) -> dict[str, Any]:
        if updated is not None:
            return updated
        if current is None:
            raise NotFoundError("Release não encontrada")
        raise self._conflict(current.get("version", 1))

    def _response(
        self, user: User, project: dict[str, Any], release: dict[str, Any]
    ) -> ReleaseResponse:
        status = ReleaseStatus(release["status"])
        checklist = release.get("checklist", [])
        history = release.get("history", [])
        users = self.users.find_by_ids(
            [item["doneBy"] for item in checklist if item.get("doneBy")]
            + [entry["userId"] for entry in history if entry.get("userId")]
        )

        def summary(user_id: ObjectId | None) -> UserSummary | None:
            document = users.get(user_id) if user_id else None
            return UserSummary.from_document(document) if document else None

        plans = self.plans.find_many_by_ids(release.get("testPlanIds", []))
        writable = not is_archived(project)
        return ReleaseResponse(
            **_summary(release).model_dump(),
            description=release.get("description", ""),
            notes=release.get("notes", ""),
            issues=self._issue_refs(release.get("issueIds", [])),
            known_bugs=self._issue_refs(release.get("knownBugIds", [])),
            test_plans=[
                TestPlanRef(id=str(plan["_id"]), name=plan["name"], status=plan["status"])
                for plan in (plans.get(plan_id) for plan_id in release.get("testPlanIds", []))
                if plan is not None
            ],
            checklist=[
                ChecklistItem(
                    id=item["id"],
                    label=item["label"],
                    required=bool(item.get("required")),
                    done=bool(item.get("done")),
                    done_by=summary(item.get("doneBy")),
                    done_at=item.get("doneAt"),
                )
                for item in checklist
            ],
            criteria=ReleaseCriteria.model_validate(
                {**DEFAULT_CRITERIA, **release.get("criteria", {})}
            ),
            quality=self._quality(release),
            history=[
                ReleaseHistoryEntry(
                    action=entry["action"],
                    from_status=entry.get("fromStatus"),
                    to_status=entry.get("toStatus"),
                    fields=entry.get("fields", []),
                    comment=entry.get("comment", ""),
                    user=summary(entry.get("userId")),
                    at=entry["at"],
                )
                for entry in reversed(history)
            ],
            can_edit=writable
            and status in EDITABLE_STATUSES
            and user.has_permissions(Permission.RELEASES_MANAGE),
            available_transitions=[
                target
                for (source, target), transition in TRANSITIONS.items()
                if writable and source is status and can_transition(user, transition)
            ],
        )


def _summary(release: dict[str, Any]) -> ReleaseSummary:
    checklist = release.get("checklist", [])
    planned: datetime | None = release.get("plannedDate")
    return ReleaseSummary(
        id=str(release["_id"]),
        project_id=str(release["projectId"]),
        name=release["name"],
        status=release["status"],
        planned_date=planned.date() if planned else None,
        released_at=release.get("releasedAt"),
        issue_count=len(release.get("issueIds", [])),
        known_bug_count=len(release.get("knownBugIds", [])),
        checklist_done=sum(1 for item in checklist if item.get("done")),
        checklist_total=len(checklist),
        created_at=release["createdAt"],
        updated_at=release["updatedAt"],
        version=release.get("version", 1),
    )


def _release_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise BusinessRuleError("Campo obrigatório", field="name")
    if not RELEASE_NAME_PATTERN.fullmatch(name):
        raise BusinessRuleError(
            "Use apenas letras, números e os caracteres . _ + - (ex.: 1.4.0)", field="name"
        )
    return name


def _duplicate_name(name: str) -> ConflictError:
    return ConflictError(f"Já existe uma release {name} neste projeto", field="name")


def _new_item(label: str, required: bool) -> dict[str, Any]:
    return {
        "id": secrets.token_hex(6),
        "label": label,
        "required": required,
        "done": False,
        "doneBy": None,
        "doneAt": None,
    }


def _checklist(
    items: list[ChecklistItemInput],
    current: list[dict[str, Any]],
    user: User,
    now: datetime,
) -> list[dict[str, Any]]:
    """Normaliza a checklist; quem marca e quando é sempre definido pelo servidor."""
    existing = {item["id"]: item for item in current}
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for data in items:
        label = " ".join(data.label.split())
        if not label:
            raise BusinessRuleError(
                "Os itens da checklist precisam de descrição", field="checklist"
            )
        previous = existing.get(data.id) if data.id else None
        if data.id and data.id in seen:
            raise BusinessRuleError("Itens da checklist repetidos", field="checklist")
        item = (
            _new_item(label, data.required)
            if previous is None
            else {
                **previous,
                "label": label,
                "required": data.required,
            }
        )
        seen.add(item["id"])
        if data.done and not item.get("done"):
            item.update(done=True, doneBy=user.id, doneAt=now)
        elif not data.done:
            item.update(done=False, doneBy=None, doneAt=None)
        result.append(item)
    return result


def _history(
    action: str,
    user: User,
    now: datetime,
    *,
    from_status: ReleaseStatus | None = None,
    to_status: ReleaseStatus | None = None,
    fields: list[str] | None = None,
    comment: str = "",
) -> dict[str, Any]:
    entry: dict[str, Any] = {"action": action, "userId": user.id, "at": now}
    if from_status is not None:
        entry["fromStatus"] = from_status.value
    if to_status is not None:
        entry["toStatus"] = to_status.value
    if fields:
        entry["fields"] = fields
    if comment:
        entry["comment"] = comment
    return entry
