import re
import time
import uuid
from http import HTTPStatus

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

REQUEST_ID_HEADER = "X-Request-ID"
# Accept a caller's ID (e.g. from the reverse proxy) only if it is short and log-safe.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = structlog.get_logger(__name__)


class RequestContextMiddleware:
    """Gives every request an ID, logs it, and turns unhandled exceptions into a 500 envelope.

    Pure ASGI (not BaseHTTPMiddleware) so it works with streaming responses such as SSE.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("request.unhandled_exception")
            if response_started:
                raise
            response = error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "An unexpected error occurred.",
                {"requestId": request_id},
            )
            await response(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request.completed",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()

    @staticmethod
    def _request_id(scope: Scope) -> str:
        for name, value in scope["headers"]:
            if name == REQUEST_ID_HEADER.lower().encode():
                candidate: str = value.decode("latin-1")
                if _VALID_REQUEST_ID.match(candidate):
                    return candidate
        return uuid.uuid4().hex
