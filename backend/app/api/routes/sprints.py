from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from app.api.deps import get_db, parse_object_id, require_permissions
from app.domain.permissions import Permission
from app.domain.sprints import SprintStatus
from app.domain.users import User
from app.schemas.common import Page, PageParams, parse_sort
from app.schemas.sprints import (
    SprintClose,
    SprintCommitment,
    SprintCreate,
    SprintIssuesAdd,
    SprintResponse,
    SprintStart,
    SprintUpdate,
)
from app.services.sprint_lifecycle import SprintLifecycleService
from app.services.sprint_planning import SprintPlanningService
from app.services.sprints import DEFAULT_SPRINT_SORT, SPRINT_SORT_FIELDS, SprintService

router = APIRouter(prefix="/sprints", tags=["sprints"])

can_read = require_permissions(Permission.PROJECTS_READ)
can_manage = require_permissions(Permission.SPRINTS_MANAGE)


def get_sprint_service(db: Database = Depends(get_db)) -> SprintService:
    return SprintService(db)


def get_planning_service(db: Database = Depends(get_db)) -> SprintPlanningService:
    return SprintPlanningService(db)


def get_lifecycle_service(db: Database = Depends(get_db)) -> SprintLifecycleService:
    return SprintLifecycleService(db)


@router.get("", response_model=Page[SprintResponse])
def list_sprints(
    response: Response,
    project_id: str = Query(alias="projectId"),
    status_filter: list[SprintStatus] = Query(default_factory=list, alias="status"),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: SprintService = Depends(get_sprint_service),
) -> Page[SprintResponse]:
    response.headers["Cache-Control"] = "no-store"
    items, total = service.search(
        user,
        parse_object_id(project_id, "Projeto"),
        statuses=list(dict.fromkeys(status_filter)),
        sort=parse_sort(sort, SPRINT_SORT_FIELDS, DEFAULT_SPRINT_SORT),
        page=page,
    )
    return Page[SprintResponse](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("", response_model=SprintResponse, status_code=status.HTTP_201_CREATED)
def create_sprint(
    data: SprintCreate,
    user: User = Depends(can_manage),
    service: SprintService = Depends(get_sprint_service),
) -> SprintResponse:
    return service.create(user, data)


@router.get("/{sprint_id}", response_model=SprintResponse)
def get_sprint(
    sprint_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: SprintService = Depends(get_sprint_service),
) -> SprintResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get(user, parse_object_id(sprint_id, "Sprint"))


@router.patch("/{sprint_id}", response_model=SprintResponse)
def update_sprint(
    sprint_id: str,
    data: SprintUpdate,
    user: User = Depends(can_manage),
    service: SprintService = Depends(get_sprint_service),
) -> SprintResponse:
    return service.update(user, parse_object_id(sprint_id, "Sprint"), data)


@router.post("/{sprint_id}/issues", response_model=SprintResponse)
def add_sprint_issues(
    sprint_id: str,
    data: SprintIssuesAdd,
    user: User = Depends(can_manage),
    service: SprintPlanningService = Depends(get_planning_service),
) -> SprintResponse:
    return service.add_issues(user, parse_object_id(sprint_id, "Sprint"), data)


@router.delete("/{sprint_id}/issues/{issue_id}", response_model=SprintResponse)
def remove_sprint_issue(
    sprint_id: str,
    issue_id: str,
    user: User = Depends(can_manage),
    service: SprintPlanningService = Depends(get_planning_service),
) -> SprintResponse:
    return service.remove_issue(
        user, parse_object_id(sprint_id, "Sprint"), parse_object_id(issue_id, "Issue")
    )


@router.post("/{sprint_id}/start", response_model=SprintResponse)
def start_sprint(
    sprint_id: str,
    data: SprintStart,
    user: User = Depends(can_manage),
    service: SprintLifecycleService = Depends(get_lifecycle_service),
) -> SprintResponse:
    return service.start(user, parse_object_id(sprint_id, "Sprint"), data)


@router.post("/{sprint_id}/close", response_model=SprintResponse)
def close_sprint(
    sprint_id: str,
    data: SprintClose,
    user: User = Depends(can_manage),
    service: SprintLifecycleService = Depends(get_lifecycle_service),
) -> SprintResponse:
    return service.close(user, parse_object_id(sprint_id, "Sprint"), data)


@router.get("/{sprint_id}/commitment", response_model=SprintCommitment)
def get_sprint_commitment(
    sprint_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: SprintLifecycleService = Depends(get_lifecycle_service),
) -> SprintCommitment:
    response.headers["Cache-Control"] = "no-store"
    return service.commitment(user, parse_object_id(sprint_id, "Sprint"))
