from collections.abc import Callable

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, Request
from pymongo.database import Database

from app.core.config import Settings
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import hash_token, tokens_equal
from app.domain.permissions import Permission
from app.domain.users import User
from app.services.auth import AuthenticatedSession, AuthService

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "X-CSRF-Token"
_AUTH_STATE = "auth_session"


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_auth_service(
    db: Database = Depends(get_db), settings: Settings = Depends(get_app_settings)
) -> AuthService:
    return AuthService(db, settings)


def client_ip(request: Request) -> str | None:
    # Com proxy_headers, o Uvicorn já substitui pelo IP real enviado pelo Nginx.
    return request.client.host if request.client else None


def _resolve_auth(request: Request, settings: Settings) -> AuthenticatedSession | None:
    """Resolve a sessão do cookie uma única vez por pedido (só acede à BD se houver cookie)."""
    if not hasattr(request.state, _AUTH_STATE):
        token = request.cookies.get(settings.session_cookie_name)
        auth = AuthService(get_db(request), settings).authenticate(token) if token else None
        setattr(request.state, _AUTH_STATE, auth)
    return getattr(request.state, _AUTH_STATE)


def get_optional_auth(
    request: Request, settings: Settings = Depends(get_app_settings)
) -> AuthenticatedSession | None:
    return _resolve_auth(request, settings)


def get_auth(
    auth: AuthenticatedSession | None = Depends(get_optional_auth),
) -> AuthenticatedSession:
    if auth is None:
        raise UnauthorizedError("Sessão inexistente ou expirada")
    return auth


def get_current_user(auth: AuthenticatedSession = Depends(get_auth)) -> User:
    return auth.user


def require_permissions(*permissions: Permission) -> Callable[..., User]:
    """Dependência que exige sessão válida e todas as permissões indicadas."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.has_permissions(*permissions):
            raise ForbiddenError("Não tem permissão para esta operação")
        return user

    return dependency


def require_any_permission(*permissions: Permission) -> Callable[..., User]:
    """Dependência que exige sessão válida e pelo menos uma das permissões indicadas."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not any(user.has_permissions(permission) for permission in permissions):
            raise ForbiddenError("Não tem permissão para esta operação")
        return user

    return dependency


def parse_object_id(value: str, resource: str = "Recurso") -> ObjectId:
    """IDs em caminhos de URL: um ID mal formado é tratado como inexistente (404)."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as error:
        raise NotFoundError(f"{resource} não encontrado") from error


def verify_csrf(request: Request, settings: Settings = Depends(get_app_settings)) -> None:
    """Proteção CSRF para métodos não seguros.

    O cabeçalho ``X-CSRF-Token`` tem de coincidir com o cookie CSRF (double submit) e, havendo
    sessão, com o token associado a essa sessão no servidor. Métodos seguros não acedem à BD.
    """
    if request.method in SAFE_METHODS:
        return
    header = request.headers.get(CSRF_HEADER, "")
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    if not header or not cookie or not tokens_equal(header, cookie):
        raise ForbiddenError("Token CSRF inválido ou em falta")
    auth = _resolve_auth(request, settings)
    if auth is not None and not tokens_equal(hash_token(header), auth.session["csrfTokenHash"]):
        raise ForbiddenError("Token CSRF inválido ou em falta")
