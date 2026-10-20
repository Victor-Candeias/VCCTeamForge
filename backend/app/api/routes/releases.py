from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from app.api.deps import get_db, parse_object_id, require_permissions
from app.domain.permissions import Permission
from app.domain.releases import ReleaseStatus
from app.domain.users import User
from app.schemas.common import Page, PageParams, parse_sort
from app.schemas.issue_search import SEARCH_TEXT_MAX_LENGTH
from app.schemas.releases import (
    ReleaseCreate,
    ReleaseResponse,
    ReleaseSummary,
    ReleaseTransition,
    ReleaseUpdate,
)
from app.services.releases import DEFAULT_RELEASE_SORT, RELEASE_SORT_FIELDS, ReleaseService

router = APIRouter(prefix="/releases", tags=["releases"])

can_read = require_permissions(Permission.RELEASES_READ)
can_manage = require_permissions(Permission.RELEASES_MANAGE)


def get_release_service(db: Database = Depends(get_db)) -> ReleaseService:
    return ReleaseService(db)


@router.get("", response_model=Page[ReleaseSummary])
def list_releases(
    response: Response,
    project_id: str = Query(alias="projectId"),
    status_filter: list[ReleaseStatus] = Query(default_factory=list, alias="status"),
    q: str | None = Query(default=None, max_length=SEARCH_TEXT_MAX_LENGTH),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: ReleaseService = Depends(get_release_service),
) -> Page[ReleaseSummary]:
    response.headers["Cache-Control"] = "no-store"
    items, total = service.search(
        user,
        parse_object_id(project_id, "Projeto"),
        statuses=list(dict.fromkeys(status_filter)),
        text=(q or "").strip() or None,
        sort=parse_sort(sort, RELEASE_SORT_FIELDS, DEFAULT_RELEASE_SORT),
        page=page,
    )
    return Page[ReleaseSummary](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("", response_model=ReleaseResponse, status_code=status.HTTP_201_CREATED)
def create_release(
    data: ReleaseCreate,
    user: User = Depends(can_manage),
    service: ReleaseService = Depends(get_release_service),
) -> ReleaseResponse:
    return service.create(user, data)


@router.get("/{release_id}", response_model=ReleaseResponse)
def get_release(
    release_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: ReleaseService = Depends(get_release_service),
) -> ReleaseResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get(user, parse_object_id(release_id, "Release"))


@router.patch("/{release_id}", response_model=ReleaseResponse)
def update_release(
    release_id: str,
    data: ReleaseUpdate,
    user: User = Depends(can_manage),
    service: ReleaseService = Depends(get_release_service),
) -> ReleaseResponse:
    return service.update(user, parse_object_id(release_id, "Release"), data)


@router.post("/{release_id}/transitions", response_model=ReleaseResponse)
def transition_release(
    release_id: str,
    data: ReleaseTransition,
    user: User = Depends(can_read),
    service: ReleaseService = Depends(get_release_service),
) -> ReleaseResponse:
    return service.transition(user, parse_object_id(release_id, "Release"), data)
