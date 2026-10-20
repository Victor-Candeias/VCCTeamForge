"""Execuções de testes, evidências, bugs a partir de falhas e progresso dos planos (DEV-021)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.attachments import IMAGE_CONTENT_TYPES
from app.domain.issues import TITLE_MAX_LENGTH, IssueType
from app.domain.permissions import Permission
from app.domain.projects import can_manage_project, is_archived
from app.domain.qa import (
    TEST_RUN_BUGS_MAX,
    TestCaseStatus,
    TestPlanStatus,
    TestRunResult,
    can_edit_test_run,
    can_execute_tests,
    case_key,
    pass_rate,
)
from app.domain.users import User
from app.repositories.attachments import AttachmentRepository
from app.repositories.qa import TestPlanRepository, TestRunRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserSummary
from app.schemas.common import PageParams
from app.schemas.issues import IssueCreate
from app.schemas.qa import (
    TestCaseRef,
    TestPlanCaseProgress,
    TestPlanProgress,
    TestRunBugCreate,
    TestRunCreate,
    TestRunEvidence,
    TestRunResponse,
    TestRunSummary,
    TestRunUpdate,
)
from app.services.attachments import AttachmentContent, store_upload
from app.services.issues import IssueService
from app.services.qa import _QaService
from app.storage.attachments import AttachmentStorage, InvalidStorageKeyError

logger = logging.getLogger(__name__)

TEST_RUN_SORT_FIELDS = {"executedAt": "executedAt"}
DEFAULT_TEST_RUN_SORT = "-executedAt"

# Tolerância para relógios ligeiramente adiantados nos postos.
EXECUTED_AT_CLOCK_SKEW = timedelta(minutes=5)

_RUN_TRACKED = ("result", "environment")
_RUN_TEXT = ("actualResult", "notes")
_BUG_DESCRIPTION_STEP_LIMIT = 50


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class TestRunService(_QaService):
    __test__ = False
    entity_label = "Execução"

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.plans = TestPlanRepository(db)
        self.runs = TestRunRepository(db)
        self.users = UserRepository(db)
        self.attachments = AttachmentRepository(db)
        self.issue_service = IssueService(db)

    # Leitura -------------------------------------------------------------------------------

    def search(
        self,
        user: User,
        project_id: ObjectId,
        *,
        test_case_id: ObjectId | None,
        test_plan_id: ObjectId | None,
        results: list[TestRunResult],
        executed_by: ObjectId | None,
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[TestRunSummary], int]:
        self._get_project(user, project_id)
        query: dict[str, Any] = {"projectId": project_id}
        if test_case_id is not None:
            query["testCaseId"] = test_case_id
        if test_plan_id is not None:
            query["testPlanId"] = test_plan_id
        if results:
            query["result"] = {"$in": [result.value for result in results]}
        if executed_by is not None:
            query["executedBy"] = executed_by
        documents = self.runs.search(query, sort=sort, skip=page.skip, limit=page.page_size)
        return self._summaries(documents), self.runs.count(query)

    def get(self, user: User, test_run_id: ObjectId) -> TestRunResponse:
        run, project = self.get_owned(user, test_run_id)
        return self._response(user, project, run)

    def get_owned(self, user: User, test_run_id: ObjectId) -> tuple[dict[str, Any], dict[str, Any]]:
        document = self.runs.find_by_id(test_run_id)
        if document is None:
            raise NotFoundError("Execução não encontrada")
        try:
            project = self._get_project(user, document["projectId"])
        except NotFoundError as error:
            raise NotFoundError("Execução não encontrada") from error
        return document, project

    # Escrita -------------------------------------------------------------------------------

    def create(self, user: User, data: TestRunCreate) -> TestRunResponse:
        if not can_execute_tests(user):
            raise ForbiddenError("Não tem permissão para registar execuções")
        test_case = self._test_case_for_run(user, data.test_case_id)
        project = self._get_project(user, test_case["projectId"])
        self._ensure_writable_project(project)
        plan = self._plan_for_run(test_case, data.test_plan_id)

        now = datetime.now(UTC)
        executed_at = now
        if data.executed_at is not None:
            executed_at = _aware(data.executed_at).astimezone(UTC)
            if executed_at > now + EXECUTED_AT_CLOCK_SKEW:
                raise BusinessRuleError(
                    "A data de execução não pode estar no futuro", field="executedAt"
                )
        document: dict[str, Any] = {
            "projectId": project["_id"],
            "testCaseId": test_case["_id"],
            "testCaseNumber": test_case["number"],
            "testCaseTitle": test_case["title"],
            "testPlanId": plan["_id"] if plan else None,
            "result": data.result.value,
            "actualResult": data.actual_result.strip(),
            "notes": data.notes.strip(),
            "environment": self._clean_text(data.environment, "environment"),
            "executedBy": user.id,
            "executedAt": executed_at,
            "bugIssueIds": [],
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        run = self.runs.create(document)
        self._audit(
            "test_run.created",
            "test_run",
            user,
            project,
            run,
            now,
            {"testCaseKey": case_key(run["testCaseNumber"]), "result": run["result"]},
        )
        return self._response(user, project, run)

    def update(self, user: User, test_run_id: ObjectId, data: TestRunUpdate) -> TestRunResponse:
        run, project = self.get_owned(user, test_run_id)
        if not can_edit_test_run(user, run):
            raise ForbiddenError("Só o executor ou quem gere testes pode alterar a execução")
        self._ensure_writable_project(project)

        provided = data.model_fields_set - {"version"}
        changes: dict[str, Any] = {}
        if "result" in provided:
            if data.result is None:
                raise BusinessRuleError("O resultado é obrigatório", field="result")
            changes["result"] = data.result.value
        if "actual_result" in provided:
            changes["actualResult"] = (data.actual_result or "").strip()
        if "notes" in provided:
            changes["notes"] = (data.notes or "").strip()
        if "environment" in provided:
            changes["environment"] = self._clean_text(data.environment, "environment")

        diff = self._diff(run, changes, _RUN_TRACKED, _RUN_TEXT)
        if not diff:
            if run.get("version", 1) != data.version:
                raise self._conflict(run.get("version", 1))
            return self._response(user, project, run)

        now = datetime.now(UTC)
        updated = self.runs.update_versioned(test_run_id, data.version, now=now, set_fields=changes)
        updated = self._require_updated(updated, self.runs.find_by_id(test_run_id))
        self._audit(
            "test_run.updated",
            "test_run",
            user,
            project,
            updated,
            now,
            {"testCaseKey": case_key(updated["testCaseNumber"]), "changes": diff},
        )
        return self._response(user, project, updated)

    def create_bug(
        self, user: User, test_run_id: ObjectId, data: TestRunBugCreate
    ) -> TestRunResponse:
        """Cria um bug a partir de uma execução falhada e liga-o à execução."""
        run, project = self.get_owned(user, test_run_id)
        if run["result"] != TestRunResult.FAIL:
            raise BusinessRuleError(
                "Só é possível criar bugs a partir de execuções falhadas", field="result"
            )
        if len(run.get("bugIssueIds", [])) >= TEST_RUN_BUGS_MAX:
            raise BusinessRuleError(
                f"A execução já tem o máximo de {TEST_RUN_BUGS_MAX} bugs ligados"
            )
        test_case = self.cases.find_by_id(run["testCaseId"]) or {}
        key = case_key(run["testCaseNumber"])
        title = (data.title or "").strip() or f"Falha em {key}: {run['testCaseTitle']}"
        issue = self.issue_service.create(
            user,
            IssueCreate(
                project_id=str(project["_id"]),
                type=IssueType.BUG,
                title=title[:TITLE_MAX_LENGTH],
                description=self._bug_description(run, test_case),
                priority=data.priority or test_case.get("priority"),
                assignee_id=data.assignee_id,
            ),
        )

        now = datetime.now(UTC)
        issue_id = ObjectId(issue.id)
        updated = self.runs.add_bug(test_run_id, issue_id, now=now, max_bugs=TEST_RUN_BUGS_MAX)
        if updated is None:
            # Limite atingido em concorrência: o bug fica criado, mas sem ligação.
            logger.warning("Bug %s criado sem ligação à execução %s", issue.key, test_run_id)
            raise ConflictError(
                f"O bug {issue.key} foi criado, mas a execução atingiu o limite de bugs ligados"
            )
        self._audit(
            "test_run.bug_created",
            "test_run",
            user,
            project,
            updated,
            now,
            {"testCaseKey": key, "issueId": issue.id, "issueKey": issue.key},
        )
        return self._response(user, project, updated)

    # Progresso do plano --------------------------------------------------------------------

    def plan_progress(self, user: User, test_plan_id: ObjectId) -> TestPlanProgress:
        plan = self.plans.find_by_id(test_plan_id)
        if plan is None:
            raise NotFoundError("Plano de teste não encontrado")
        try:
            self._get_project(user, plan["projectId"])
        except NotFoundError as error:
            raise NotFoundError("Plano de teste não encontrado") from error

        test_case_ids: list[ObjectId] = plan.get("testCaseIds", [])
        found = self.cases.find_many_by_ids(test_case_ids)
        latest = self.runs.latest_by_case(plan["_id"])
        executors = self.users.find_by_ids(
            [runs[0]["executedBy"] for runs in latest.values() if runs]
        )

        counts = {result: 0 for result in TestRunResult}
        cases: list[TestPlanCaseProgress] = []
        for test_case_id in test_case_ids:
            test_case = found.get(test_case_id)
            if test_case is None:
                continue
            runs = latest.get(test_case_id, [])
            last = runs[0] if runs else None
            previous = runs[1] if len(runs) > 1 else None
            last_result = TestRunResult(last["result"]) if last else TestRunResult.NOT_RUN
            previous_result = TestRunResult(previous["result"]) if previous else None
            counts[last_result] += 1
            executor = executors.get(last["executedBy"]) if last else None
            cases.append(
                TestPlanCaseProgress(
                    test_case=TestCaseRef(
                        id=str(test_case["_id"]),
                        key=case_key(test_case["number"]),
                        title=test_case["title"],
                        priority=test_case["priority"],
                        status=test_case["status"],
                    ),
                    last_run_id=str(last["_id"]) if last else None,
                    last_result=last_result,
                    last_executed_at=last["executedAt"] if last else None,
                    last_executed_by=UserSummary.from_document(executor) if executor else None,
                    previous_result=previous_result,
                    regression=previous_result is TestRunResult.PASS
                    and last_result is TestRunResult.FAIL,
                )
            )
        return TestPlanProgress(
            test_plan_id=str(plan["_id"]),
            total_cases=len(cases),
            counts=counts,
            executed_cases=sum(1 for item in cases if item.last_run_id is not None),
            pass_rate=pass_rate({result.value: count for result, count in counts.items()}),
            regressions=sum(1 for item in cases if item.regression),
            cases=cases,
        )

    # Auxiliares ----------------------------------------------------------------------------

    def _conflict(self, current_version: int) -> ConflictError:
        return ConflictError(
            "A execução foi alterada entretanto. Recarregue e tente novamente.",
            currentVersion=current_version,
        )

    def _require_updated(
        self, updated: dict[str, Any] | None, current: dict[str, Any] | None
    ) -> dict[str, Any]:
        if updated is not None:
            return updated
        if current is None:
            raise NotFoundError("Execução não encontrada")
        raise self._conflict(current.get("version", 1))

    def _test_case_for_run(self, user: User, raw_id: str) -> dict[str, Any]:
        if not ObjectId.is_valid(raw_id):
            raise BusinessRuleError("Identificador inválido em testCaseId", field="testCaseId")
        test_case = self.cases.find_by_id(ObjectId(raw_id))
        try:
            if test_case is None:
                raise NotFoundError("Caso de teste não encontrado")
            self._get_project(user, test_case["projectId"])
        except NotFoundError as error:
            raise BusinessRuleError(
                "Caso de teste inexistente ou sem acesso", field="testCaseId"
            ) from error
        if test_case["status"] == TestCaseStatus.DEPRECATED:
            raise BusinessRuleError(
                f"O caso {case_key(test_case['number'])} está obsoleto", field="testCaseId"
            )
        return test_case

    def _plan_for_run(self, test_case: dict[str, Any], raw_id: str | None) -> dict[str, Any] | None:
        if not raw_id:
            return None
        if not ObjectId.is_valid(raw_id):
            raise BusinessRuleError("Identificador inválido em testPlanId", field="testPlanId")
        plan = self.plans.find_by_id(ObjectId(raw_id))
        if plan is None or plan["projectId"] != test_case["projectId"]:
            raise BusinessRuleError(
                "O plano tem de existir e pertencer ao projeto", field="testPlanId"
            )
        if plan["status"] == TestPlanStatus.CLOSED:
            raise BusinessRuleError("O plano está fechado", field="testPlanId")
        if test_case["_id"] not in plan.get("testCaseIds", []):
            raise BusinessRuleError("O caso não pertence ao plano", field="testPlanId")
        return plan

    @staticmethod
    def _bug_description(run: dict[str, Any], test_case: dict[str, Any]) -> str:
        key = case_key(run["testCaseNumber"])
        lines = [f"Bug encontrado na execução do caso de teste **{key}** — {run['testCaseTitle']}."]
        if run.get("environment"):
            lines.append(f"\n**Ambiente:** {run['environment']}")
        if test_case.get("preconditions"):
            lines.append(f"\n**Pré-condições**\n\n{test_case['preconditions']}")
        steps = test_case.get("steps", [])[:_BUG_DESCRIPTION_STEP_LIMIT]
        if steps:
            lines.append("\n**Passos**\n")
            lines.extend(f"{index}. {step['action']}" for index, step in enumerate(steps, 1))
        if test_case.get("expectedResult"):
            lines.append(f"\n**Resultado esperado**\n\n{test_case['expectedResult']}")
        if run.get("actualResult"):
            lines.append(f"\n**Resultado obtido**\n\n{run['actualResult']}")
        if run.get("notes"):
            lines.append(f"\n**Observações**\n\n{run['notes']}")
        return "\n".join(lines)[:5000]

    def _summaries(self, documents: list[dict[str, Any]]) -> list[TestRunSummary]:
        context = self._context(documents)
        return [TestRunSummary(**self._summary_fields(document, context)) for document in documents]

    def _context(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        plans = self.plans.names_by_ids([d["testPlanId"] for d in documents if d.get("testPlanId")])
        return {
            "plans": plans,
            "users": self.users.find_by_ids([d["executedBy"] for d in documents]),
            "evidences": self.attachments.count_by_test_run([d["_id"] for d in documents]),
        }

    @staticmethod
    def _summary_fields(document: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        executor = context["users"].get(document.get("executedBy"))
        plan_id = document.get("testPlanId")
        return {
            "id": str(document["_id"]),
            "project_id": str(document["projectId"]),
            "test_case_id": str(document["testCaseId"]),
            "test_case_key": case_key(document["testCaseNumber"]),
            "test_case_title": document["testCaseTitle"],
            "test_plan_id": str(plan_id) if plan_id else None,
            "test_plan_name": context["plans"].get(plan_id) if plan_id else None,
            "result": document["result"],
            "environment": document.get("environment", ""),
            "executed_by": UserSummary.from_document(executor) if executor else None,
            "executed_at": document["executedAt"],
            "bug_count": len(document.get("bugIssueIds", [])),
            "evidence_count": context["evidences"].get(document["_id"], 0),
            "version": document.get("version", 1),
        }

    def _response(
        self, user: User, project: dict[str, Any], document: dict[str, Any]
    ) -> TestRunResponse:
        writable = not is_archived(project)
        can_edit = writable and can_edit_test_run(user, document)
        return TestRunResponse(
            **self._summary_fields(document, self._context([document])),
            actual_result=document.get("actualResult", ""),
            notes=document.get("notes", ""),
            bugs=self._issue_refs(document.get("bugIssueIds", [])),
            created_at=document["createdAt"],
            updated_at=document["updatedAt"],
            can_edit=can_edit,
            can_add_evidence=can_edit,
            can_create_bug=writable
            and document["result"] == TestRunResult.FAIL
            and user.has_permissions(Permission.ISSUES_WRITE)
            and len(document.get("bugIssueIds", [])) < TEST_RUN_BUGS_MAX,
        )


class TestRunEvidenceService:
    """Evidências em anexo das execuções (mesma validação e armazenamento dos anexos)."""

    __test__ = False

    def __init__(self, db: Database, settings: Settings) -> None:
        self.settings = settings
        self.runs = TestRunService(db)
        self.attachments = AttachmentRepository(db)
        self.users = UserRepository(db)
        self.storage = AttachmentStorage(settings.attachments_path)

    def list_evidences(self, user: User, test_run_id: ObjectId) -> list[TestRunEvidence]:
        run, project = self.runs.get_owned(user, test_run_id)
        return self._to_evidences(user, project, self.attachments.list_for_test_run(run["_id"]))

    def upload(
        self, user: User, test_run_id: ObjectId, filename: str | None, source: BinaryIO
    ) -> TestRunEvidence:
        run, project = self.runs.get_owned(user, test_run_id)
        if not can_edit_test_run(user, run):
            raise ForbiddenError("Só o executor ou quem gere testes pode adicionar evidências")
        self.runs._ensure_writable_project(project)
        limit = self.settings.attachments_max_per_issue
        if self.attachments.count_for_test_run(run["_id"]) >= limit:
            raise BusinessRuleError(
                f"A execução já tem o máximo de {limit} evidências", field="file"
            )
        upload = store_upload(self.storage, self.settings, str(run["projectId"]), filename, source)
        document = {
            "testRunId": run["_id"],
            "issueId": None,
            "projectId": run["projectId"],
            "uploadedBy": user.id,
            "originalName": upload.original_name,
            "storageKey": upload.stored.storage_key,
            "contentType": upload.content_type,
            "size": upload.stored.size,
            "sha256": upload.stored.sha256,
            "createdAt": upload.now,
            "updatedAt": upload.now,
            "deletedAt": None,
            "deletedBy": None,
        }
        try:
            evidence = self.attachments.create(document)
        except PyMongoError:
            self.storage.delete(upload.stored.storage_key)
            raise
        self._audit("test_run_evidence.created", user, project, run, evidence)
        return self._to_evidences(user, project, [evidence])[0]

    def get_content(
        self, user: User, test_run_id: ObjectId, evidence_id: ObjectId
    ) -> AttachmentContent:
        run, _ = self.runs.get_owned(user, test_run_id)
        evidence = self._find(evidence_id, run["_id"])
        try:
            path = self.storage.path_for(evidence["storageKey"])
        except InvalidStorageKeyError as error:
            raise NotFoundError("Evidência não encontrada") from error
        if not path.is_file():
            logger.error("Ficheiro da evidência %s em falta no disco", evidence["_id"])
            raise NotFoundError("Evidência não encontrada")
        return AttachmentContent(
            path=path,
            original_name=evidence["originalName"],
            content_type=evidence["contentType"],
            is_image=evidence["contentType"] in IMAGE_CONTENT_TYPES,
        )

    def delete(self, user: User, test_run_id: ObjectId, evidence_id: ObjectId) -> None:
        run, project = self.runs.get_owned(user, test_run_id)
        evidence = self._find(evidence_id, run["_id"])
        if not self._can_delete(user, project, evidence):
            raise ForbiddenError(
                "Só quem carregou, quem gere testes ou o responsável do projeto pode remover"
            )
        self.runs._ensure_writable_project(project)
        if (
            self.attachments.soft_delete(evidence["_id"], actor_id=user.id, now=datetime.now(UTC))
            is None
        ):
            raise NotFoundError("Evidência não encontrada")
        try:
            self.storage.delete(evidence["storageKey"])
        except (OSError, InvalidStorageKeyError):
            logger.exception("Não foi possível apagar o ficheiro da evidência %s", evidence["_id"])
        self._audit("test_run_evidence.deleted", user, project, run, evidence)

    # Auxiliares ----------------------------------------------------------------------------

    def _find(self, evidence_id: ObjectId, test_run_id: ObjectId) -> dict[str, Any]:
        evidence = self.attachments.find_active_evidence(evidence_id, test_run_id)
        if evidence is None:
            raise NotFoundError("Evidência não encontrada")
        return evidence

    @staticmethod
    def _can_delete(user: User, project: dict[str, Any], evidence: dict[str, Any]) -> bool:
        if user.has_permissions(Permission.TESTS_MANAGE) or can_manage_project(user, project):
            return True
        return can_execute_tests(user) and evidence.get("uploadedBy") == user.id

    def _audit(
        self,
        action: str,
        user: User,
        project: dict[str, Any],
        run: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        self.runs.audit.record(
            action,
            now=datetime.now(UTC),
            actor_id=user.id,
            entity_type="test_run",
            entity_id=run["_id"],
            details={
                "projectKey": project["key"],
                "testCaseKey": case_key(run["testCaseNumber"]),
                "evidenceId": str(evidence["_id"]),
                "name": evidence["originalName"],
                "size": evidence["size"],
            },
        )

    def _to_evidences(
        self, user: User, project: dict[str, Any], documents: list[dict[str, Any]]
    ) -> list[TestRunEvidence]:
        uploaders = self.users.find_by_ids(
            [d["uploadedBy"] for d in documents if d.get("uploadedBy")]
        )
        writable = not is_archived(project)
        result = []
        for document in documents:
            uploader = uploaders.get(document.get("uploadedBy"))
            result.append(
                TestRunEvidence(
                    id=str(document["_id"]),
                    test_run_id=str(document["testRunId"]),
                    original_name=document["originalName"],
                    content_type=document["contentType"],
                    size=document["size"],
                    sha256=document["sha256"],
                    is_image=document["contentType"] in IMAGE_CONTENT_TYPES,
                    uploaded_by=UserSummary.from_document(uploader) if uploader else None,
                    created_at=document["createdAt"],
                    can_delete=writable and self._can_delete(user, project, document),
                )
            )
        return result
