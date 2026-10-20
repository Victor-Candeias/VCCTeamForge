from fastapi import APIRouter, Depends, Request, Response, status

from app.api.cookies import clear_session_cookies, set_csrf_cookie, set_session_cookies
from app.api.deps import client_ip, get_app_settings, get_auth_service, get_optional_auth
from app.core.config import Settings
from app.core.security import new_token
from app.schemas.auth import CsrfTokenResponse, CurrentUserResponse, LoginRequest
from app.services.auth import AuthenticatedSession, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/csrf", response_model=CsrfTokenResponse)
def get_csrf_token(
    request: Request, response: Response, settings: Settings = Depends(get_app_settings)
) -> CsrfTokenResponse:
    """Devolve (e define, se faltar) o token CSRF necessário para o login."""
    token = request.cookies.get(settings.csrf_cookie_name)
    if not token:
        token = new_token()
        set_csrf_cookie(response, settings, token)
    response.headers.update(NO_STORE)
    return CsrfTokenResponse(csrf_token=token)


@router.post("/login", response_model=CurrentUserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_app_settings),
    service: AuthService = Depends(get_auth_service),
    current: AuthenticatedSession | None = Depends(get_optional_auth),
) -> CurrentUserResponse:
    result = service.login(
        payload.email,
        payload.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if current is not None:
        service.sessions.delete(current.session["_id"])
    set_session_cookies(response, settings, result.session_token, result.csrf_token)
    response.headers.update(NO_STORE)
    return CurrentUserResponse.from_user(result.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    settings: Settings = Depends(get_app_settings),
    service: AuthService = Depends(get_auth_service),
    current: AuthenticatedSession | None = Depends(get_optional_auth),
) -> Response:
    if current is not None:
        service.logout(current, ip=client_ip(request))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response
