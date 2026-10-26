from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import APIRouter, FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.schemas import BaseSchema, InputSchema, Page


class ProbeRead(BaseSchema):
    price_copper: int
    expires_at: datetime
    seller_character_name: str


class ProbeCreate(InputSchema):
    note: str


router = APIRouter(prefix="/probe")


@router.get("/read", response_model=Page[ProbeRead])
async def read() -> Page[ProbeRead]:
    item = ProbeRead(
        price_copper=20_000,
        expires_at=datetime(2026, 11, 4, 23, 0, tzinfo=UTC),
        seller_character_name="Ana Stormcaller",
    )
    return Page(items=[item], total=1, limit=20, offset=0)


@router.post("/create", response_model=ProbeCreate, status_code=status.HTTP_201_CREATED)
async def create(body: ProbeCreate) -> ProbeCreate:
    return body


@pytest.fixture
async def probe_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_responses_serialize_camel_case(probe_client: AsyncClient) -> None:
    response = await probe_client.get("/probe/read")

    assert response.json() == {
        "items": [
            {
                "priceCopper": 20_000,
                "expiresAt": "2026-11-04T23:00:00Z",
                "sellerCharacterName": "Ana Stormcaller",
            }
        ],
        "total": 1,
        "limit": 20,
        "offset": 0,
    }


async def test_request_bodies_accept_camel_case_and_strip_whitespace(
    probe_client: AsyncClient,
) -> None:
    response = await probe_client.post("/probe/create", json={"note": "  Summons in Org  "})

    assert response.status_code == 201
    assert response.json() == {"note": "Summons in Org"}


def test_input_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProbeCreate.model_validate({"note": "hi", "userId": "someone-else"})


def test_base_schema_builds_from_attributes() -> None:
    class Row:
        price_copper = 5
        expires_at = datetime(2026, 11, 4, tzinfo=UTC)
        seller_character_name = "Bo Ironhide"

    assert ProbeRead.model_validate(Row()).price_copper == 5


def test_page_limit_is_capped() -> None:
    with pytest.raises(ValidationError):
        Page[ProbeRead](items=[], total=0, limit=1_000, offset=0)
