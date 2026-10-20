from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from app.api.deps import get_db, parse_object_id, require_permissions
from app.domain.permissions import Permission
from app.domain.projects import ProjectStatus
from app.domain.users import User
from app.schemas.common import Page, PageParams, parse_sort
from app.schemas.projects import (
    MemberAdd,
    ProjectCreate,
    ProjectMembersResponse,
    ProjectResponse,
    ProjectUpdate,
    VersionInput,
)
from app.services.common import object_id_or_422
from app.services.projects import PROJECT_SORT_FIELDS, ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])

can_read = require_permissions(Permission.PROJECTS_READ)
can_manage = require_permissions(Permission.PROJECTS_MANAGE)


def get_project_service(db: Database = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def _project_id(project_id: str) -> ObjectId:
    return parse_object_id(project_id, "Projeto")


@router.get("", response_model=Page[ProjectResponse])
def list_projects(
    response: Response,
    status_filter: list[ProjectStatus] = Query(default_factory=list, alias="status"),
    include_archived: bool = Query(default=False, alias="includeArchived"),
    q: str | None = Query(default=None, max_length=100),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: ProjectService = Depends(get_project_service),
) -> Page[ProjectResponse]:
    response.headers["Cache-Control"] = "no-store"
    items, total = service.search(
        user,
        statuses=status_filter,
        include_archived=include_archived,
        text=q,
        sort=parse_sort(sort, PROJECT_SORT_FIELDS, "name"),
        page=page,
    )
    return Page[ProjectResponse](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    user: User = Depends(can_manage),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    return service.create(user, data)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.to_response(user, service.get_accessible(user, _project_id(project_id)))


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    user: User = Depends(can_manage),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    return service.update(user, _project_id(project_id), data)


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: str,
    data: VersionInput,
    user: User = Depends(can_manage),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    return service.archive(user, _project_id(project_id), data.version)


@router.post("/{project_id}/restore", response_model=ProjectResponse)
def restore_project(
    project_id: str,
    data: VersionInput,
    user: User = Depends(can_manage),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    return service.restore(user, _project_id(project_id), data.version)


@router.get("/{project_id}/members", response_model=ProjectMembersResponse)
def list_members(
    project_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: ProjectService = Depends(get_project_service),
) -> ProjectMembersResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.members(user, _project_id(project_id))


@router.post("/{project_id}/members", response_model=ProjectMembersResponse)
def add_member(
    project_id: str,
    data: MemberAdd,
    user: User = Depends(can_manage),
    service: ProjectService = Depends(get_project_service),
) -> ProjectMembersResponse:
    member_id = object_id_or_422(data.user_id, "userId")
    return service.add_member(user, _project_id(project_id), member_id, data.version)


@router.delete("/{project_id}/members/{member_id}", response_model=ProjectMembersResponse)
def remove_member(
    project_id: str,
    member_id: str,
    version: int = Query(ge=1),
    user: User = Depends(can_manage),
    service: ProjectService = Depends(get_project_service),
) -> ProjectMembersResponse:
    return service.remove_member(
        user, _project_id(project_id), parse_object_id(member_id, "Membro"), version
    )
