from fastapi import Response

from app.core.config import Settings


def _cookie_options(settings: Settings) -> dict:
    return {
        "path": "/",
        "secure": bool(settings.cookie_secure),
        "samesite": settings.cookie_samesite,
    }


def set_csrf_cookie(response: Response, settings: Settings, token: str) -> None:
    # Legível pelo JavaScript (double submit); não dá acesso à sessão.
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        max_age=settings.session_absolute_hours * 3600,
        httponly=False,
        **_cookie_options(settings),
    )


def set_session_cookies(
    response: Response, settings: Settings, session_token: str, csrf_token: str
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_absolute_hours * 3600,
        httponly=True,
        **_cookie_options(settings),
    )
    set_csrf_cookie(response, settings, csrf_token)


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, httponly=True, **_cookie_options(settings))
    response.delete_cookie(settings.csrf_cookie_name, **_cookie_options(settings))
