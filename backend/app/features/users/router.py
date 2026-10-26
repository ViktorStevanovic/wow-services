from fastapi import APIRouter, status

from app.core.errors import NotAuthenticatedError, error_responses
from app.features.auth.dependencies import CurrentUserDep
from app.features.users.dependencies import UserServiceDep
from app.features.users.exceptions import AccountSuspendedError
from app.features.users.schemas import MeRead

router = APIRouter(prefix="/me", tags=["me"])


@router.get(
    "",
    response_model=MeRead,
    status_code=status.HTTP_200_OK,
    summary="Current user",
    description="The signed-in user's account.",
    responses=error_responses(NotAuthenticatedError, AccountSuspendedError),
)
async def get_me(user: CurrentUserDep, service: UserServiceDep) -> MeRead:
    return await service.get_me(user.id)
