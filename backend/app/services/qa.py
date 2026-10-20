"""Casos e planos de teste (DEV-020)."""

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.common import PRIORITY_RANK, Priority
from app.domain.issues import IssueRuleError, normalize_labels
from app.domain.projects import is_archived
from app.domain.qa import (
    TEST_CASE_KEY_PATTERN,
    TestCaseStatus,
    TestPlanStatus,
    can_manage_tests,
    case_counter_name,
    case_key,
    plan_name_key,
)
from app.domain.users import User
from app.repositories.audit import AuditLogRepository
from app.repositories.counters import CounterRepository
from app.repositories.issues import IssueRepository
from app.repositories.projects import ProjectRepository
from app.repositories.qa import TestCaseRepository, TestPlanNameExistsError, TestPlanRepository
from app.schemas.common import PageParams
from app.schemas.issues import IssueRef
from app.schemas.qa import (
    TestCaseCreate,
    TestCaseRef,
    TestCaseResponse,
    TestCaseSummary,
    TestCaseUpdate,
    TestPlanCreate,
    TestPlanResponse,
    TestPlanSummary,
    TestPlanUpdate,
    TestStep,
)
from app.services.authorization import ensure_project_access
from app.services.common import jsonable

TEST_CASE_SORT_FIELDS = {
    "number": "number",
    "title": "title",
    "priority": "priorityRank",
    "updatedAt": "updatedAt",
}
DEFAULT_TEST_CASE_SORT = "number"
TEST_PLAN_SORT_FIELDS = {"name": "nameKey", "createdAt": "createdAt", "updatedAt": "updatedAt"}
DEFAULT_TEST_PLAN_SORT = "-createdAt"

# Campos cujas alterações ficam na auditoria (textos longos só indicam que mudaram).
_CASE_TRACKED = ("title", "priority", "status", "labels", "issueIds")
_CASE_TEXT = ("description", "preconditions", "steps", "expectedResult")
_PLAN_TRACKED = ("name", "status", "issueIds")
_PLAN_TEXT = ("description", "testCaseIds")

_SUMMARY_PROJECTION = {
    "projectId": 1,
    "number": 1,
    "title": 1,
    "priority": 1,
    "status": 1,
    "labels": 1,
    "stepCount": 1,
    "updatedAt": 1,
    "version": 1,
}


class _QaService:
    entity_label = ""

    def __init__(self, db: Database) -> None:
        self.projects = ProjectRepository(db)
        self.issues = IssueRepository(db)
        self.cases = TestCaseRepository(db)
        self.audit = AuditLogRepository(db)

    # Projeto e permissões ------------------------------------------------------------------

    @staticmethod
    def _ensure_can_manage(user: User) -> None:
        if not can_manage_tests(user):
            raise ForbiddenError("Não tem permissão para gerir testes")

    def _project_for_write(self, user: User, raw_project_id: str) -> dict[str, Any]:
        if not ObjectId.is_valid(raw_project_id):
            raise BusinessRuleError("Identificador inválido em projectId", field="projectId")
        try:
            project = self._get_project(user, ObjectId(raw_project_id))
        except NotFoundError as error:
            raise BusinessRuleError(
                "Projeto inexistente ou sem acesso", field="projectId"
            ) from error
        self._ensure_writable_project(project)
        return project

    def _get_project(self, user: User, project_id: ObjectId) -> dict[str, Any]:
        return dict(ensure_project_access(user, self.projects.find_by_id(project_id)))

    def _get_owned(
        self, user: User, document: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if document is None:
            raise NotFoundError(f"{self.entity_label} não encontrado")
        try:
            project = self._get_project(user, document["projectId"])
        except NotFoundError as error:
            raise NotFoundError(f"{self.entity_label} não encontrado") from error
        return document, project

    @staticmethod
    def _ensure_writable_project(project: dict[str, Any]) -> None:
        if is_archived(project):
            raise BusinessRuleError("O projeto está arquivado e só pode ser consultado")

    @staticmethod
    def _writable(user: User, project: dict[str, Any]) -> bool:
        return can_manage_tests(user) and not is_archived(project)

    # Ligações ------------------------------------------------------------------------------

    @staticmethod
    def _object_ids(values: Iterable[str], field: str) -> list[ObjectId]:
        """Converte e remove repetidos mantendo a ordem."""
        result: list[ObjectId] = []
        for value in values:
            if not ObjectId.is_valid(value):
                raise BusinessRuleError(f"Identificador inválido em {field}", field=field)
            object_id = ObjectId(value)
            if object_id not in result:
                result.append(object_id)
        return result

    def _resolve_issue_ids(self, project_id: ObjectId, values: Iterable[str]) -> list[ObjectId]:
        issue_ids = self._object_ids(values, "issueIds")
        found = self.issues.find_many_by_ids(issue_ids)
        for issue_id in issue_ids:
            issue = found.get(issue_id)
            if issue is None or issue["projectId"] != project_id:
                raise BusinessRuleError(
                    "As issues ligadas têm de existir e pertencer ao projeto", field="issueIds"
                )
        return issue_ids

    def _issue_refs(self, issue_ids: list[ObjectId]) -> list[IssueRef]:
        found = self.issues.find_many_by_ids(issue_ids)
        return [
            IssueRef(
                id=str(issue["_id"]),
                key=issue["key"],
                title=issue["title"],
                type=issue["type"],
                status=issue["status"],
            )
            for issue in (found.get(issue_id) for issue_id in issue_ids)
            if issue is not None
        ]

    # Escrita comum -------------------------------------------------------------------------

    @staticmethod
    def _clean_text(value: str | None, field: str, *, required: bool = False) -> str:
        text = " ".join((value or "").split())
        if required and not text:
            raise BusinessRuleError("Campo obrigatório", field=field)
        return text

    @staticmethod
    def _diff(
        current: dict[str, Any],
        changes: dict[str, Any],
        tracked: tuple[str, ...],
        text_fields: tuple[str, ...],
    ) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for field, value in changes.items():
            if current.get(field) == value:
                continue
            if field in tracked:
                diff[field] = {"from": jsonable(current.get(field)), "to": jsonable(value)}
            elif field in text_fields:
                diff[field] = {"changed": True}
        return diff

    def _conflict(self, current_version: int) -> ConflictError:
        return ConflictError(
            f"O {self.entity_label.lower()} foi alterado entretanto. Recarregue e tente novamente.",
            currentVersion=current_version,
        )

    def _require_updated(
        self, updated: dict[str, Any] | None, current: dict[str, Any] | None
    ) -> dict[str, Any]:
        if updated is not None:
            return updated
        if current is None:
            raise NotFoundError(f"{self.entity_label} não encontrado")
        raise self._conflict(current.get("version", 1))

    def _audit(
        self,
        action: str,
        entity_type: str,
        user: User,
        project: dict[str, Any],
        document: dict[str, Any],
        now: datetime,
        details: dict[str, Any],
    ) -> None:
        self.audit.record(
            action,
            now=now,
            actor_id=user.id,
            entity_type=entity_type,
            entity_id=document["_id"],
            details={"projectKey": project["key"], **details},
        )


def _labels(values: Iterable[str]) -> list[str]:
    try:
        return normalize_labels(values)
    except IssueRuleError as error:
        raise BusinessRuleError(str(error), field=error.field) from error


def _steps(steps: Iterable[TestStep]) -> list[dict[str, str]]:
    result = []
    for step in steps:
        action = step.action.strip()
        if not action:
            raise BusinessRuleError("Cada passo precisa de uma ação", field="steps")
        result.append({"action": action, "expectedResult": step.expected_result.strip()})
    return result


class TestCaseService(_QaService):
    __test__ = False
    entity_label = "Caso de teste"

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.counters = CounterRepository(db)

    def search(
        self,
        user: User,
        project_id: ObjectId,
        *,
        statuses: list[TestCaseStatus],
        priorities: list[Priority],
        labels: list[str],
        issue_id: ObjectId | None,
        text: str | None,
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[TestCaseSummary], int]:
        self._get_project(user, project_id)
        query: dict[str, Any] = {"projectId": project_id}
        if statuses:
            query["status"] = {"$in": [status.value for status in statuses]}
        if priorities:
            query["priority"] = {"$in": [priority.value for priority in priorities]}
        if labels:
            try:
                query["labels"] = {"$in": normalize_labels(labels)}
            except IssueRuleError as error:
                raise BusinessRuleError(str(error), field="label") from error
        if issue_id is not None:
            query["issueIds"] = issue_id
        if text:
            title = {"title": {"$regex": re.escape(text), "$options": "i"}}
            match = TEST_CASE_KEY_PATTERN.fullmatch(text)
            if match:
                query["$or"] = [{"number": int(match.group(1))}, title]
            else:
                query.update(title)
        documents = self.cases.search(
            query,
            sort=sort,
            skip=page.skip,
            limit=page.page_size,
            projection=_SUMMARY_PROJECTION,
        )
        return [self._summary(document) for document in documents], self.cases.count(query)

    def get(self, user: User, test_case_id: ObjectId) -> TestCaseResponse:
        test_case, project = self._get_owned(user, self.cases.find_by_id(test_case_id))
        return self._response(user, project, test_case)

    def create(self, user: User, data: TestCaseCreate) -> TestCaseResponse:
        self._ensure_can_manage(user)
        project = self._project_for_write(user, data.project_id)
        project_id = project["_id"]
        steps = _steps(data.steps)
        labels = _labels(data.labels)
        issue_ids = self._resolve_issue_ids(project_id, data.issue_ids)
        title = self._clean_text(data.title, "title", required=True)

        now = datetime.now(UTC)
        number = self.counters.next_value(case_counter_name(project_id))
        document: dict[str, Any] = {
            "projectId": project_id,
            "number": number,
            "title": title,
            "description": data.description.strip(),
            "preconditions": data.preconditions.strip(),
            "steps": steps,
            "stepCount": len(steps),
            "expectedResult": data.expected_result.strip(),
            "priority": data.priority.value,
            "priorityRank": PRIORITY_RANK[data.priority],
            "status": data.status.value,
            "labels": labels,
            "issueIds": issue_ids,
            "createdBy": user.id,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        test_case = self.cases.create(document)
        self._audit(
            "test_case.created",
            "test_case",
            user,
            project,
            test_case,
            now,
            {"key": case_key(number), "title": title},
        )
        return self._response(user, project, test_case)

    def update(self, user: User, test_case_id: ObjectId, data: TestCaseUpdate) -> TestCaseResponse:
        self._ensure_can_manage(user)
        test_case, project = self._get_owned(user, self.cases.find_by_id(test_case_id))
        self._ensure_writable_project(project)

        provided = data.model_fields_set - {"version"}
        changes: dict[str, Any] = {}
        if "title" in provided:
            changes["title"] = self._clean_text(data.title, "title", required=True)
        for field, attribute in (
            ("description", "description"),
            ("preconditions", "preconditions"),
            ("expectedResult", "expected_result"),
        ):
            if attribute in provided:
                changes[field] = (getattr(data, attribute) or "").strip()
        if "steps" in provided:
            if not data.steps:
                raise BusinessRuleError("Indique pelo menos um passo", field="steps")
            changes["steps"] = _steps(data.steps)
            changes["stepCount"] = len(changes["steps"])
        if "priority" in provided:
            if data.priority is None:
                raise BusinessRuleError("A prioridade é obrigatória", field="priority")
            changes["priority"] = data.priority.value
            changes["priorityRank"] = PRIORITY_RANK[data.priority]
        if "status" in provided:
            if data.status is None:
                raise BusinessRuleError("O estado é obrigatório", field="status")
            changes["status"] = data.status.value
        if "labels" in provided:
            changes["labels"] = _labels(data.labels or [])
        if "issue_ids" in provided:
            changes["issueIds"] = self._resolve_issue_ids(project["_id"], data.issue_ids or [])

        diff = self._diff(test_case, changes, _CASE_TRACKED, _CASE_TEXT)
        if not diff:
            if test_case.get("version", 1) != data.version:
                raise self._conflict(test_case.get("version", 1))
            return self._response(user, project, test_case)

        now = datetime.now(UTC)
        updated = self.cases.update_versioned(
            test_case_id, data.version, now=now, set_fields=changes
        )
        updated = self._require_updated(updated, self.cases.find_by_id(test_case_id))
        self._audit(
            "test_case.updated",
            "test_case",
            user,
            project,
            updated,
            now,
            {"key": case_key(updated["number"]), "changes": diff},
        )
        return self._response(user, project, updated)

    # Conversão -----------------------------------------------------------------------------

    @staticmethod
    def _summary_fields(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(document["_id"]),
            "project_id": str(document["projectId"]),
            "key": case_key(document["number"]),
            "number": document["number"],
            "title": document["title"],
            "priority": document["priority"],
            "status": document["status"],
            "labels": document.get("labels", []),
            "step_count": document.get("stepCount", 0),
            "updated_at": document["updatedAt"],
            "version": document.get("version", 1),
        }

    def _summary(self, document: dict[str, Any]) -> TestCaseSummary:
        return TestCaseSummary(**self._summary_fields(document))

    def _response(
        self, user: User, project: dict[str, Any], document: dict[str, Any]
    ) -> TestCaseResponse:
        return TestCaseResponse(
            **self._summary_fields(document),
            description=document.get("description", ""),
            preconditions=document.get("preconditions", ""),
            steps=[
                TestStep(action=step["action"], expected_result=step.get("expectedResult", ""))
                for step in document.get("steps", [])
            ],
            expected_result=document.get("expectedResult", ""),
            issues=self._issue_refs(document.get("issueIds", [])),
            created_at=document["createdAt"],
            can_edit=self._writable(user, project),
        )


class TestPlanService(_QaService):
    __test__ = False
    entity_label = "Plano de teste"

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.plans = TestPlanRepository(db)

    def search(
        self,
        user: User,
        project_id: ObjectId,
        *,
        statuses: list[TestPlanStatus],
        text: str | None,
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[TestPlanSummary], int]:
        self._get_project(user, project_id)
        query: dict[str, Any] = {"projectId": project_id}
        if statuses:
            query["status"] = {"$in": [status.value for status in statuses]}
        if text:
            query["name"] = {"$regex": re.escape(text), "$options": "i"}
        documents = self.plans.search(query, sort=sort, skip=page.skip, limit=page.page_size)
        return [self._summary(document) for document in documents], self.plans.count(query)

    def get(self, user: User, test_plan_id: ObjectId) -> TestPlanResponse:
        plan, project = self._get_owned(user, self.plans.find_by_id(test_plan_id))
        return self._response(user, project, plan)

    def create(self, user: User, data: TestPlanCreate) -> TestPlanResponse:
        self._ensure_can_manage(user)
        project = self._project_for_write(user, data.project_id)
        project_id = project["_id"]
        name = self._clean_text(data.name, "name", required=True)
        test_case_ids = self._resolve_test_case_ids(project_id, data.test_case_ids, [])
        issue_ids = self._resolve_issue_ids(project_id, data.issue_ids)

        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "projectId": project_id,
            "name": name,
            "nameKey": plan_name_key(name),
            "description": data.description.strip(),
            "status": data.status.value,
            "testCaseIds": test_case_ids,
            "issueIds": issue_ids,
            "createdBy": user.id,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        try:
            plan = self.plans.create(document)
        except TestPlanNameExistsError as error:
            raise self._duplicate_name(name) from error
        self._audit("test_plan.created", "test_plan", user, project, plan, now, {"name": name})
        return self._response(user, project, plan)

    def update(self, user: User, test_plan_id: ObjectId, data: TestPlanUpdate) -> TestPlanResponse:
        self._ensure_can_manage(user)
        plan, project = self._get_owned(user, self.plans.find_by_id(test_plan_id))
        self._ensure_writable_project(project)

        provided = data.model_fields_set - {"version"}
        if "status" in provided and data.status is None:
            raise BusinessRuleError("O estado é obrigatório", field="status")
        if plan["status"] == TestPlanStatus.CLOSED and provided - {"status"}:
            raise BusinessRuleError(
                "O plano está fechado: reabra-o antes de o alterar", field="status"
            )

        changes: dict[str, Any] = {}
        if "name" in provided:
            changes["name"] = self._clean_text(data.name, "name", required=True)
            changes["nameKey"] = plan_name_key(changes["name"])
        if "description" in provided:
            changes["description"] = (data.description or "").strip()
        if "status" in provided and data.status is not None:
            changes["status"] = data.status.value
        if "test_case_ids" in provided:
            changes["testCaseIds"] = self._resolve_test_case_ids(
                project["_id"], data.test_case_ids or [], plan.get("testCaseIds", [])
            )
        if "issue_ids" in provided:
            changes["issueIds"] = self._resolve_issue_ids(project["_id"], data.issue_ids or [])

        diff = self._diff(plan, changes, _PLAN_TRACKED, _PLAN_TEXT)
        if not diff:
            if plan.get("version", 1) != data.version:
                raise self._conflict(plan.get("version", 1))
            return self._response(user, project, plan)

        now = datetime.now(UTC)
        try:
            updated = self.plans.update_versioned(
                test_plan_id, data.version, now=now, set_fields=changes
            )
        except TestPlanNameExistsError as error:
            raise self._duplicate_name(changes["name"]) from error
        updated = self._require_updated(updated, self.plans.find_by_id(test_plan_id))
        self._audit(
            "test_plan.updated", "test_plan", user, project, updated, now, {"changes": diff}
        )
        return self._response(user, project, updated)

    # Auxiliares ----------------------------------------------------------------------------

    def _resolve_test_case_ids(
        self, project_id: ObjectId, values: Iterable[str], current: list[ObjectId]
    ) -> list[ObjectId]:
        """Valida os casos; os que entram de novo no plano não podem estar obsoletos."""
        test_case_ids = self._object_ids(values, "testCaseIds")
        found = self.cases.find_many_by_ids(test_case_ids)
        for test_case_id in test_case_ids:
            test_case = found.get(test_case_id)
            if test_case is None or test_case["projectId"] != project_id:
                raise BusinessRuleError(
                    "Os casos de teste têm de existir e pertencer ao projeto", field="testCaseIds"
                )
            if test_case["status"] == TestCaseStatus.DEPRECATED and test_case_id not in current:
                raise BusinessRuleError(
                    f"O caso {case_key(test_case['number'])} está obsoleto",
                    field="testCaseIds",
                )
        return test_case_ids

    @staticmethod
    def _duplicate_name(name: str) -> ConflictError:
        return ConflictError(
            f"Já existe um plano de teste com o nome {name} neste projeto", field="name"
        )

    @staticmethod
    def _summary_fields(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(document["_id"]),
            "project_id": str(document["projectId"]),
            "name": document["name"],
            "description": document.get("description", ""),
            "status": document["status"],
            "test_case_count": len(document.get("testCaseIds", [])),
            "created_at": document["createdAt"],
            "updated_at": document["updatedAt"],
            "version": document.get("version", 1),
        }

    def _summary(self, document: dict[str, Any]) -> TestPlanSummary:
        return TestPlanSummary(**self._summary_fields(document))

    def _response(
        self, user: User, project: dict[str, Any], document: dict[str, Any]
    ) -> TestPlanResponse:
        test_case_ids: list[ObjectId] = document.get("testCaseIds", [])
        found = self.cases.find_many_by_ids(test_case_ids)
        test_cases = [
            TestCaseRef(
                id=str(test_case["_id"]),
                key=case_key(test_case["number"]),
                title=test_case["title"],
                priority=test_case["priority"],
                status=test_case["status"],
            )
            for test_case in (found.get(test_case_id) for test_case_id in test_case_ids)
            if test_case is not None
        ]
        return TestPlanResponse(
            **self._summary_fields(document),
            test_cases=test_cases,
            issues=self._issue_refs(document.get("issueIds", [])),
            can_edit=self._writable(user, project),
        )
