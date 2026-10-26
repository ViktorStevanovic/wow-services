"""Domain exceptions (raised by services) and the handlers that turn them into HTTP errors.

Services import only the exception classes. Everything HTTP-related lives in the handlers
below, so the status code of each error type is decided in one place.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.schemas import ErrorBody, ErrorResponse


class AppError(Exception):
    """Base for every domain error. Subclasses set a stable `code` and a default `message`."""

    code: str = "app_error"
    message: str = "Something went wrong."

    def __init__(
        self, message: str | None = None, *, details: dict[str, JsonValue] | None = None
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class NotAuthenticatedError(AppError):
    code = "not_authenticated"
    message = "You need to sign in."


class ForbiddenError(AppError):
    code = "forbidden"
    message = "You are not allowed to do this."


class NotFoundError(AppError):
    code = "not_found"
    message = "Not found."


class ConflictError(AppError):
    code = "conflict"
    message = "This conflicts with the current state."


class BusinessRuleError(AppError):
    code = "business_rule_violation"
    message = "This request breaks a rule."


class UpstreamServiceError(AppError):
    """An external service (e.g. the Blizzard API) failed or can't serve the request."""

    code = "upstream_error"
    message = "An external service is unavailable. Try again later."


# Most specific class first: the first match wins.
_STATUS_BY_ERROR: tuple[tuple[type[AppError], HTTPStatus], ...] = (
    (NotAuthenticatedError, HTTPStatus.UNAUTHORIZED),
    (ForbiddenError, HTTPStatus.FORBIDDEN),
    (NotFoundError, HTTPStatus.NOT_FOUND),
    (ConflictError, HTTPStatus.CONFLICT),
    (BusinessRuleError, HTTPStatus.UNPROCESSABLE_ENTITY),
    (UpstreamServiceError, HTTPStatus.BAD_GATEWAY),
)

_CODE_BY_HTTP_STATUS = {
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
}


def status_for(error: AppError) -> HTTPStatus:
    for error_type, status in _STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return status
    return HTTPStatus.INTERNAL_SERVER_ERROR


def error_response(
    status: int,
    code: str,
    message: str,
    details: dict[str, JsonValue] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}))
    return JSONResponse(
        status_code=int(status),
        content=body.model_dump(mode="json", by_alias=True),
        headers=headers,
    )


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(status_for(exc), exc.code, exc.message, exc.details)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Pydantic error dicts are loosely typed; keep only the safe parts (never echo `input`).
    errors: list[dict[str, Any]] = list(exc.errors())
    fields: list[JsonValue] = [
        {"loc": [str(part) for part in err["loc"]], "message": err["msg"], "type": err["type"]}
        for err in errors
    ]
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "validation_error",
        "The request is invalid.",
        {"fields": fields},
    )


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    """Framework-raised HTTP errors (unknown route, wrong method...)."""
    assert isinstance(exc, StarletteHTTPException)
    status = HTTPStatus(exc.status_code)
    return error_response(
        status,
        _CODE_BY_HTTP_STATUS.get(status, f"http_{status.value}"),
        str(exc.detail) if exc.detail else status.phrase,
        headers=exc.headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    # Unhandled exceptions become a 500 in RequestContextMiddleware, which knows the request ID.
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)


def error_responses(*errors: type[AppError] | HTTPStatus) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` for a route, e.g. `error_responses(NotFoundError, ConflictError)`."""
    responses: dict[int | str, dict[str, Any]] = {}
    for error in errors:
        status = error if isinstance(error, HTTPStatus) else status_for(error())
        responses[status.value] = {"model": ErrorResponse, "description": status.phrase}
    return responses
