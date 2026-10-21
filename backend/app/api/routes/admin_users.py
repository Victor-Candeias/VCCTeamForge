"""Gestão de utilizadores pelo Administrador (DEV-028)."""

from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from app.api.deps import get_auth, get_db, parse_object_id, require_permissions
from app.domain.permissions import Permission, Role
from app.domain.users import User, UserStatus
from app.schemas.common import Page, PageParams, parse_sort
from app.schemas.users import PasswordReset, UserAdminResponse, UserCreate, UserUpdate
from app.services.auth import AuthenticatedSession
from app.services.users import USER_SORT_FIELDS, UserService

router = APIRouter(prefix="/admin/users", tags=["admin"])

can_manage = require_permissions(Permission.USERS_MANAGE)


def get_user_service(db: Database = Depends(get_db)) -> UserService:
    return UserService(db)


def _user_id(user_id: str) -> ObjectId:
    return parse_object_id(user_id, "Utilizador")


@router.get("", response_model=Page[UserAdminResponse])
def list_users(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    role: list[Role] = Query(default_factory=list),
    status_filter: list[UserStatus] = Query(default_factory=list, alias="status"),
    sort: str | None = Query(default=None, max_length=30),
    page: PageParams = Depends(),
    _: User = Depends(can_manage),
    service: UserService = Depends(get_user_service),
) -> Page[UserAdminResponse]:
    response.headers["Cache-Control"] = "no-store"
    items, total = service.search(
        text=q,
        roles=role,
        statuses=status_filter,
        sort=parse_sort(sort, USER_SORT_FIELDS, "name"),
        page=page,
    )
    return Page[UserAdminResponse](
        items=items, total=total, page=page.page, page_size=page.page_size
    )


@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    actor: User = Depends(can_manage),
    service: UserService = Depends(get_user_service),
) -> UserAdminResponse:
    return service.create(actor, data)


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: str,
    response: Response,
    _: User = Depends(can_manage),
    service: UserService = Depends(get_user_service),
) -> UserAdminResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get(_user_id(user_id))


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: str,
    data: UserUpdate,
    actor: User = Depends(can_manage),
    service: UserService = Depends(get_user_service),
) -> UserAdminResponse:
    return service.update(actor, _user_id(user_id), data)


@router.post("/{user_id}/password", response_model=UserAdminResponse)
def reset_password(
    user_id: str,
    data: PasswordReset,
    actor: User = Depends(can_manage),
    auth: AuthenticatedSession = Depends(get_auth),
    service: UserService = Depends(get_user_service),
) -> UserAdminResponse:
    return service.reset_password(
        actor, _user_id(user_id), data, current_session_id=auth.session["_id"]
    )
