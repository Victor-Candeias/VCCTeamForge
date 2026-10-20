import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import PROBLEM_JSON, build_problem
from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """Atribui um request id (aceita o do Nginx se válido), regista cada pedido e converte
    exceções não tratadas numa resposta 500 RFC 7807 sem expor detalhes internos."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, REQUEST_ID_HEADER)
        request_id = (
            incoming if incoming and _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("Erro não tratado em %s %s", scope["method"], scope["path"])
            if response_started:
                raise
            body = build_problem(500, scope["path"], "Erro interno", "Ocorreu um erro inesperado.")
            response = JSONResponse(body, status_code=500, media_type=PROBLEM_JSON)
            await response(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            client = scope.get("client")
            logger.info(
                "%s %s %s %.1fms",
                scope["method"],
                scope["path"],
                status_code,
                duration_ms,
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "durationMs": duration_ms,
                    "client": client[0] if client else None,
                },
            )
            request_id_var.reset(token)


def _header(scope: Scope, name: str) -> str | None:
    encoded = name.encode("latin-1")
    for key, value in scope.get("headers", []):
        if key == encoded:
            return value.decode("latin-1")
    return None
