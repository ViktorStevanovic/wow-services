import asyncio

import structlog
from sqlalchemy import literal
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.features.health.enums import ComponentStatus, HealthStatus
from app.features.health.schemas import HealthRead

logger = structlog.get_logger(__name__)

DATABASE_CHECK_TIMEOUT_SECONDS = 2.0


class HealthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(self) -> HealthRead:
        database = await self._check_database()
        status = HealthStatus.OK if database is ComponentStatus.OK else HealthStatus.DEGRADED
        return HealthRead(status=status, database=database)

    async def _check_database(self) -> ComponentStatus:
        try:
            async with asyncio.timeout(DATABASE_CHECK_TIMEOUT_SECONDS):
                await self._session.exec(select(literal(1)))
        except (SQLAlchemyError, OSError, TimeoutError):
            logger.warning("health.database_unavailable", exc_info=True)
            return ComponentStatus.UNAVAILABLE
        return ComponentStatus.OK
