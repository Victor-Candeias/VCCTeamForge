from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from app.api.deps import get_db, parse_object_id, require_permissions
from app.core.errors import BusinessRuleError
from app.domain.common import Priority
from app.domain.permissions import Permission
from app.domain.qa import TestCaseStatus, TestPlanStatus
from app.domain.users import User
from app.schemas.common import Page, PageParams, parse_sort
from app.schemas.issue_search import SEARCH_TEXT_MAX_LENGTH
from app.schemas.qa import (
    TestCaseCreate,
    TestCaseResponse,
    TestCaseSummary,
    TestCaseUpdate,
    TestPlanCreate,
    TestPlanResponse,
    TestPlanSummary,
    TestPlanUpdate,
)
from app.services.qa import (
    DEFAULT_TEST_CASE_SORT,
    DEFAULT_TEST_PLAN_SORT,
    TEST_CASE_SORT_FIELDS,
    TEST_PLAN_SORT_FIELDS,
    TestCaseService,
    TestPlanService,
)

router = APIRouter(tags=["tests"])

can_read = require_permissions(Permission.TESTS_READ)
can_manage = require_permissions(Permission.TESTS_MANAGE)


def get_test_case_service(db: Database = Depends(get_db)) -> TestCaseService:
    return TestCaseService(db)


def get_test_plan_service(db: Database = Depends(get_db)) -> TestPlanService:
    return TestPlanService(db)


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
