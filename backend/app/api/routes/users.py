from fastapi import APIRouter, Depends, Query, Response
from pymongo.database import Database

from app.api.deps import get_current_user, get_db, require_any_permission
from app.domain.permissions import Permission
from app.domain.users import User
from app.repositories.users import UserRepository
from app.schemas.auth import CurrentUserResponse, UserSummary

router = APIRouter(prefix="/users", tags=["users"])

USER_SEARCH_LIMIT = 20


@router.get("/me", response_model=CurrentUserResponse)
def get_me(response: Response, user: User = Depends(get_current_user)) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    return CurrentUserResponse.from_user(user)


@router.get("", response_model=list[UserSummary])
def search_users(
    response: Response,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=USER_SEARCH_LIMIT, ge=1, le=USER_SEARCH_LIMIT),
    _: User = Depends(require_any_permission(Permission.PROJECTS_MANAGE, Permission.USERS_MANAGE)),
    db: Database = Depends(get_db),
) -> list[UserSummary]:
    """Utilizadores ativos para escolher membros/responsáveis (não expõe dados de autenticação)."""
    response.headers["Cache-Control"] = "no-store"
    return [
        UserSummary.from_document(document)
        for document in UserRepository(db).search_active(q, limit)
    ]
