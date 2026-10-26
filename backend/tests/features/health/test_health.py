from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.db import create_session_factory
from app.features.health.enums import ComponentStatus, HealthStatus
from app.features.health.service import HealthService
from tests.conftest import TEST_DATABASE_URL

UNREACHABLE_DATABASE_URL = "postgresql+asyncpg://forever:forever@127.0.0.1:1/nothing"


async def test_service_reports_ok_when_database_reachable() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with create_session_factory(engine)() as session:
            result = await HealthService(session).check()
    finally:
        await engine.dispose()

    assert result.status is HealthStatus.OK
    assert result.database is ComponentStatus.OK


async def test_service_reports_degraded_when_database_unreachable() -> None:
    engine = create_async_engine(UNREACHABLE_DATABASE_URL)
    try:
        async with create_session_factory(engine)() as session:
            result = await HealthService(session).check()
    finally:
        await engine.dispose()

    assert result.status is HealthStatus.DEGRADED
    assert result.database is ComponentStatus.UNAVAILABLE


async def test_get_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
