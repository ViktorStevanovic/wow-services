import logging
from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import APIRouter, FastAPI, Query
from httpx import ASGITransport, AsyncClient
from pydantic import Field

from app.core.errors import (
    AppError,
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
    UpstreamServiceError,
)
from app.core.schemas import InputSchema


class ListingAlreadyActiveError(ConflictError):
    code = "listing_already_active"
    message = "This character already has an active summon listing."


class ProbeCreate(InputSchema):
    price_copper: Annotated[int, Field(ge=0)]


router = APIRouter(prefix="/probe")


@router.get("/errors/{name}")
async def raise_domain_error(name: str) -> None:
    errors: dict[str, AppError] = {
        "not_authenticated": NotAuthenticatedError(),
        "forbidden": ForbiddenError(),
        "not_found": NotFoundError("Listing not found."),
        "conflict": ListingAlreadyActiveError(details={"serviceType": "summon"}),
        "business_rule": BusinessRuleError(),
        "upstream": UpstreamServiceError(),
    }
    raise errors[name]


@router.post("/validate")
async def validate(body: ProbeCreate, limit: Annotated[int, Query(le=100)] = 10) -> None:
    return None


@router.get("/crash")
async def crash() -> None:
    raise RuntimeError("secret internal detail")


@pytest.fixture
async def probe_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    app.include_router(router)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [
        ("not_authenticated", 401, "not_authenticated"),
        ("forbidden", 403, "forbidden"),
        ("not_found", 404, "not_found"),
        ("conflict", 409, "listing_already_active"),
        ("business_rule", 422, "business_rule_violation"),
        ("upstream", 502, "upstream_error"),
    ],
)
async def test_domain_errors_map_to_status_and_envelope(
    probe_client: AsyncClient, name: str, status: int, code: str
) -> None:
    response = await probe_client.get(f"/probe/errors/{name}")

    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code


async def test_domain_error_keeps_message_and_details(probe_client: AsyncClient) -> None:
    response = await probe_client.get("/probe/errors/conflict")

    assert response.json() == {
        "error": {
            "code": "listing_already_active",
            "message": "This character already has an active summon listing.",
            "details": {"serviceType": "summon"},
        }
    }


async def test_validation_error_uses_envelope_with_camel_case_field_paths(
    probe_client: AsyncClient,
) -> None:
    response = await probe_client.post(
        "/probe/validate?limit=500", json={"priceCopper": -1, "status": "active"}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    fields = {tuple(item["loc"]): item for item in error["details"]["fields"]}
    assert set(fields) == {("body", "priceCopper"), ("body", "status"), ("query", "limit")}
    assert fields[("body", "status")]["type"] == "extra_forbidden"
    assert all("input" not in item for item in fields.values())


async def test_unknown_route_returns_not_found_envelope(
    probe_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        response = await probe_client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    [completed] = [
        r.msg
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg["event"] == "request.completed"
    ]
    assert type(completed["status"]) is int  # a plain int in the logs, not an HTTPStatus


async def test_wrong_method_returns_method_not_allowed_envelope(
    probe_client: AsyncClient,
) -> None:
    response = await probe_client.delete("/probe/validate")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert response.headers["allow"] == "POST"


async def test_unhandled_exception_returns_generic_500_and_logs_request_id(
    probe_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = await probe_client.get("/probe/crash")

    assert response.status_code == 500
    request_id = response.headers["x-request-id"]
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {"requestId": request_id},
        }
    }
    assert "secret internal detail" not in response.text
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.msg["event"] == "request.unhandled_exception"  # type: ignore[index]  # structlog event dict
    assert record.msg["request_id"] == request_id  # type: ignore[index]
    assert record.exc_info is not None


async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert len(response.headers["x-request-id"]) == 32


async def test_request_id_reused_from_caller(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"X-Request-ID": "proxy-abc.123"})

    assert response.headers["x-request-id"] == "proxy-abc.123"


async def test_unsafe_request_id_replaced(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"X-Request-ID": "bad id; with spaces"})

    assert response.headers["x-request-id"] != "bad id; with spaces"
    assert len(response.headers["x-request-id"]) == 32


async def test_openapi_documents_validation_errors_with_envelope(
    probe_client: AsyncClient,
) -> None:
    schema = (await probe_client.get("/openapi.json")).json()

    response_422 = schema["paths"]["/probe/validate"]["post"]["responses"]["422"]
    assert response_422["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
