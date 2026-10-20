"""Erros da aplicação no formato RFC 7807 (application/problem+json)."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"


class AppError(Exception):
    status_code = 400
    title = "Pedido inválido"

    def __init__(self, detail: str | None = None, **extensions: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.extensions = extensions
        self.headers: dict[str, str] | None = None


class UnauthorizedError(AppError):
    status_code = 401
    title = "Autenticação necessária"


class ForbiddenError(AppError):
    status_code = 403
    title = "Acesso negado"


class NotFoundError(AppError):
    status_code = 404
    title = "Recurso não encontrado"


class ConflictError(AppError):
    status_code = 409
    title = "Conflito"


class BusinessRuleError(AppError):
    status_code = 422
    title = "Regra de negócio violada"


class PayloadTooLargeError(AppError):
    status_code = 413
    title = "Conteúdo demasiado grande"


class TooManyRequestsError(AppError):
    status_code = 429
    title = "Demasiados pedidos"

    def __init__(self, detail: str | None = None, retry_after: int | None = None) -> None:
        super().__init__(detail)
        if retry_after:
            self.headers = {"Retry-After": str(retry_after)}


def build_problem(
    status_code: int,
    instance: str,
    title: str | None = None,
    detail: str | None = None,
    **extensions: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title or HTTPStatus(status_code).phrase,
        "status": status_code,
    }
    if detail:
        body["detail"] = detail
    body["instance"] = instance
    body["requestId"] = request_id_var.get()
    body.update(extensions)
    return body


def problem_response(
    request: Request,
    status_code: int,
    title: str | None = None,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
    **extensions: Any,
) -> JSONResponse:
    body = build_problem(status_code, request.url.path, title, detail, **extensions)
    return JSONResponse(body, status_code=status_code, headers=headers, media_type=PROBLEM_JSON)


async def _app_error(request: Request, error: AppError) -> JSONResponse:
    return problem_response(
        request,
        error.status_code,
        error.title,
        error.detail,
        headers=error.headers,
        **error.extensions,
    )


async def _http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    detail = error.detail if isinstance(error.detail, str) else None
    if detail == HTTPStatus(error.status_code).phrase:
        detail = None
    return problem_response(request, error.status_code, detail=detail, headers=error.headers)


async def _validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    # Não devolver os valores recebidos (podem conter passwords).
    errors = [
        {"loc": list(item.get("loc", ())), "msg": item.get("msg"), "type": item.get("type")}
        for item in error.errors()
    ]
    return problem_response(
        request, 422, "Dados inválidos", "O pedido contém campos inválidos.", errors=errors
    )


async def _database_unavailable(request: Request, error: ConnectionFailure) -> JSONResponse:
    logger.error("MongoDB indisponível: %s", error)
    return problem_response(
        request, 503, "Serviço indisponível", "Base de dados indisponível. Tente novamente."
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Erros não tratados (500) são convertidos pelo RequestContextMiddleware."""
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(ConnectionFailure, _database_unavailable)
