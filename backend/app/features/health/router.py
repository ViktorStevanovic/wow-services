from fastapi import APIRouter, status

from app.features.health.dependencies import HealthServiceDep
from app.features.health.schemas import HealthRead

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthRead,
    status_code=status.HTTP_200_OK,
    summary="Service health",
    description=(
        "Reports whether the API is up and can reach the database. "
        "Always returns 200; `status` is `degraded` when a dependency is unavailable."
    ),
)
async def get_health(service: HealthServiceDep) -> HealthRead:
    return await service.check()
