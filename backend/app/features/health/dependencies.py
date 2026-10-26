from typing import Annotated

from fastapi import Depends

from app.core.dependencies import SessionDep
from app.features.health.service import HealthService


def get_health_service(session: SessionDep) -> HealthService:
    return HealthService(session)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
