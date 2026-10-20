from bson import ObjectId
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.api.deps import get_app_settings, get_db, parse_object_id, require_permissions
from app.api.routes.attachments import content_disposition
from app.core.config import Settings
from app.core.errors import BusinessRuleError
from app.domain.common import Priority
from app.domain.permissions import Permission
from app.domain.qa import TestCaseStatus, TestPlanStatus, TestRunResult
from app.domain.users import User
from app.schemas.common import Page, PageParams, parse_sort
from app.schemas.issue_search import SEARCH_TEXT_MAX_LENGTH
from app.schemas.qa import (
    TestCaseCreate,
    TestCaseResponse,
    TestCaseSummary,
    TestCaseUpdate,
    TestPlanCreate,
    TestPlanProgress,
    TestPlanResponse,
    TestPlanSummary,
    TestPlanUpdate,
    TestRunBugCreate,
    TestRunCreate,
    TestRunEvidence,
    TestRunResponse,
    TestRunSummary,
    TestRunUpdate,
)
from app.services.qa import (
    DEFAULT_TEST_CASE_SORT,
    DEFAULT_TEST_PLAN_SORT,
    TEST_CASE_SORT_FIELDS,
    TEST_PLAN_SORT_FIELDS,
    TestCaseService,
    TestPlanService,
)
from app.services.test_runs import (
    DEFAULT_TEST_RUN_SORT,
    TEST_RUN_SORT_FIELDS,
    TestRunEvidenceService,
    TestRunService,
)

router = APIRouter(tags=["tests"])

can_read = require_permissions(Permission.TESTS_READ)
can_manage = require_permissions(Permission.TESTS_MANAGE)
can_execute = require_permissions(Permission.TESTS_EXECUTE)
can_write_issues = require_permissions(Permission.ISSUES_WRITE)


def get_test_case_service(db: Database = Depends(get_db)) -> TestCaseService:
    return TestCaseService(db)


def get_test_plan_service(db: Database = Depends(get_db)) -> TestPlanService:
    return TestPlanService(db)


def get_test_run_service(db: Database = Depends(get_db)) -> TestRunService:
    return TestRunService(db)


def get_evidence_service(
    db: Database = Depends(get_db), settings: Settings = Depends(get_app_settings)
) -> TestRunEvidenceService:
    return TestRunEvidenceService(db, settings)


def _optional_object_id(value: str | None, field: str) -> ObjectId | None:
    if not value:
        return None
    if not ObjectId.is_valid(value):
        raise BusinessRuleError(f"Identificador inválido em {field}", field=field)
    return ObjectId(value)


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


# Casos de teste ----------------------------------------------------------------------------


@router.get("/test-cases", response_model=Page[TestCaseSummary])
def list_test_cases(
    response: Response,
    project_id: str = Query(alias="projectId"),
    status_filter: list[TestCaseStatus] = Query(default_factory=list, alias="status"),
    priorities: list[Priority] = Query(default_factory=list, alias="priority"),
    labels: list[str] = Query(default_factory=list, alias="label"),
    issue_id: str | None = Query(default=None, alias="issueId"),
    q: str | None = Query(default=None, max_length=SEARCH_TEXT_MAX_LENGTH),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: TestCaseService = Depends(get_test_case_service),
) -> Page[TestCaseSummary]:
    response.headers["Cache-Control"] = "no-store"
    if issue_id and not ObjectId.is_valid(issue_id):
        raise BusinessRuleError("Identificador inválido em issueId", field="issueId")
    items, total = service.search(
        user,
        parse_object_id(project_id, "Projeto"),
        statuses=list(dict.fromkeys(status_filter)),
        priorities=list(dict.fromkeys(priorities)),
        labels=labels,
        issue_id=ObjectId(issue_id) if issue_id else None,
        text=_text(q),
        sort=parse_sort(sort, TEST_CASE_SORT_FIELDS, DEFAULT_TEST_CASE_SORT),
        page=page,
    )
    return Page[TestCaseSummary](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("/test-cases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_test_case(
    data: TestCaseCreate,
    user: User = Depends(can_manage),
    service: TestCaseService = Depends(get_test_case_service),
) -> TestCaseResponse:
    return service.create(user, data)


@router.get("/test-cases/{test_case_id}", response_model=TestCaseResponse)
def get_test_case(
    test_case_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: TestCaseService = Depends(get_test_case_service),
) -> TestCaseResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get(user, parse_object_id(test_case_id, "Caso de teste"))


@router.patch("/test-cases/{test_case_id}", response_model=TestCaseResponse)
def update_test_case(
    test_case_id: str,
    data: TestCaseUpdate,
    user: User = Depends(can_manage),
    service: TestCaseService = Depends(get_test_case_service),
) -> TestCaseResponse:
    return service.update(user, parse_object_id(test_case_id, "Caso de teste"), data)


# Planos de teste ---------------------------------------------------------------------------


@router.get("/test-plans", response_model=Page[TestPlanSummary])
def list_test_plans(
    response: Response,
    project_id: str = Query(alias="projectId"),
    status_filter: list[TestPlanStatus] = Query(default_factory=list, alias="status"),
    q: str | None = Query(default=None, max_length=SEARCH_TEXT_MAX_LENGTH),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: TestPlanService = Depends(get_test_plan_service),
) -> Page[TestPlanSummary]:
    response.headers["Cache-Control"] = "no-store"
    items, total = service.search(
        user,
        parse_object_id(project_id, "Projeto"),
        statuses=list(dict.fromkeys(status_filter)),
        text=_text(q),
        sort=parse_sort(sort, TEST_PLAN_SORT_FIELDS, DEFAULT_TEST_PLAN_SORT),
        page=page,
    )
    return Page[TestPlanSummary](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("/test-plans", response_model=TestPlanResponse, status_code=status.HTTP_201_CREATED)
def create_test_plan(
    data: TestPlanCreate,
    user: User = Depends(can_manage),
    service: TestPlanService = Depends(get_test_plan_service),
) -> TestPlanResponse:
    return service.create(user, data)


@router.get("/test-plans/{test_plan_id}", response_model=TestPlanResponse)
def get_test_plan(
    test_plan_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: TestPlanService = Depends(get_test_plan_service),
) -> TestPlanResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get(user, parse_object_id(test_plan_id, "Plano de teste"))


@router.patch("/test-plans/{test_plan_id}", response_model=TestPlanResponse)
def update_test_plan(
    test_plan_id: str,
    data: TestPlanUpdate,
    user: User = Depends(can_manage),
    service: TestPlanService = Depends(get_test_plan_service),
) -> TestPlanResponse:
    return service.update(user, parse_object_id(test_plan_id, "Plano de teste"), data)


@router.get("/test-plans/{test_plan_id}/progress", response_model=TestPlanProgress)
def get_test_plan_progress(
    test_plan_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: TestRunService = Depends(get_test_run_service),
) -> TestPlanProgress:
    response.headers["Cache-Control"] = "no-store"
    return service.plan_progress(user, parse_object_id(test_plan_id, "Plano de teste"))


# Execuções ---------------------------------------------------------------------------------


@router.get("/test-runs", response_model=Page[TestRunSummary])
def list_test_runs(
    response: Response,
    project_id: str = Query(alias="projectId"),
    test_case_id: str | None = Query(default=None, alias="testCaseId"),
    test_plan_id: str | None = Query(default=None, alias="testPlanId"),
    results: list[TestRunResult] = Query(default_factory=list, alias="result"),
    executed_by: str | None = Query(default=None, alias="executedBy"),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: TestRunService = Depends(get_test_run_service),
) -> Page[TestRunSummary]:
    response.headers["Cache-Control"] = "no-store"
    executor = user.id if executed_by == "me" else _optional_object_id(executed_by, "executedBy")
    items, total = service.search(
        user,
        parse_object_id(project_id, "Projeto"),
        test_case_id=_optional_object_id(test_case_id, "testCaseId"),
        test_plan_id=_optional_object_id(test_plan_id, "testPlanId"),
        results=list(dict.fromkeys(results)),
        executed_by=executor,
        sort=parse_sort(sort, TEST_RUN_SORT_FIELDS, DEFAULT_TEST_RUN_SORT),
        page=page,
    )
    return Page[TestRunSummary](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("/test-runs", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
def create_test_run(
    data: TestRunCreate,
    user: User = Depends(can_execute),
    service: TestRunService = Depends(get_test_run_service),
) -> TestRunResponse:
    return service.create(user, data)


@router.get("/test-runs/{test_run_id}", response_model=TestRunResponse)
def get_test_run(
    test_run_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: TestRunService = Depends(get_test_run_service),
) -> TestRunResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get(user, parse_object_id(test_run_id, "Execução"))


@router.patch("/test-runs/{test_run_id}", response_model=TestRunResponse)
def update_test_run(
    test_run_id: str,
    data: TestRunUpdate,
    user: User = Depends(can_read),
    service: TestRunService = Depends(get_test_run_service),
) -> TestRunResponse:
    # A permissão (executor ou tests:manage) é verificada no serviço.
    return service.update(user, parse_object_id(test_run_id, "Execução"), data)


@router.post(
    "/test-runs/{test_run_id}/bugs",
    response_model=TestRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_test_run_bug(
    test_run_id: str,
    data: TestRunBugCreate,
    user: User = Depends(can_write_issues),
    service: TestRunService = Depends(get_test_run_service),
) -> TestRunResponse:
    return service.create_bug(user, parse_object_id(test_run_id, "Execução"), data)


@router.get("/test-runs/{test_run_id}/evidences", response_model=list[TestRunEvidence])
def list_test_run_evidences(
    test_run_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: TestRunEvidenceService = Depends(get_evidence_service),
) -> list[TestRunEvidence]:
    response.headers["Cache-Control"] = "no-store"
    return service.list_evidences(user, parse_object_id(test_run_id, "Execução"))


@router.post(
    "/test-runs/{test_run_id}/evidences",
    response_model=TestRunEvidence,
    status_code=status.HTTP_201_CREATED,
)
def upload_test_run_evidence(
    test_run_id: str,
    file: UploadFile = File(...),
    user: User = Depends(can_read),
    service: TestRunEvidenceService = Depends(get_evidence_service),
) -> TestRunEvidence:
    return service.upload(user, parse_object_id(test_run_id, "Execução"), file.filename, file.file)


@router.get("/test-runs/{test_run_id}/evidences/{evidence_id}/content")
def download_test_run_evidence(
    test_run_id: str,
    evidence_id: str,
    inline: bool = Query(default=False),
    user: User = Depends(can_read),
    service: TestRunEvidenceService = Depends(get_evidence_service),
) -> FileResponse:
    content = service.get_content(
        user,
        parse_object_id(test_run_id, "Execução"),
        parse_object_id(evidence_id, "Evidência"),
    )
    disposition = "inline" if inline and content.is_image else "attachment"
    return FileResponse(
        content.path,
        media_type=content.content_type,
        headers={
            "Content-Disposition": content_disposition(disposition, content.original_name),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(
    "/test-runs/{test_run_id}/evidences/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_test_run_evidence(
    test_run_id: str,
    evidence_id: str,
    user: User = Depends(can_read),
    service: TestRunEvidenceService = Depends(get_evidence_service),
) -> Response:
    service.delete(
        user,
        parse_object_id(test_run_id, "Execução"),
        parse_object_id(evidence_id, "Evidência"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
