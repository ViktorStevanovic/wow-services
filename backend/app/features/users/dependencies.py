from typing import Annotated

from fastapi import Depends

from app.core.dependencies import SessionDep
from app.features.users.service import UserService


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
