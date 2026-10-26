from typing import Annotated

from fastapi import Cookie, Depends

from app.core.dependencies import SessionDep, SettingsDep
from app.core.errors import NotAuthenticatedError
from app.core.security import OAUTH_STATE_COOKIE, SESSION_COOKIE
from app.features.auth.schemas import AuthenticatedUser
from app.features.auth.service import AuthService
from app.features.users.dependencies import UserServiceDep
from app.integrations.blizzard.dependencies import BlizzardProviderDep

SessionCookie = Annotated[
    str | None, Cookie(alias=SESSION_COOKIE, description="Session cookie set at sign-in.")
]
OAuthStateCookie = Annotated[str | None, Cookie(alias=OAUTH_STATE_COOKIE, include_in_schema=False)]


def get_auth_service(
    session: SessionDep,
    settings: SettingsDep,
    provider: BlizzardProviderDep,
    users: UserServiceDep,
) -> AuthService:
    return AuthService(session, settings, provider, users)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_optional_user(
    service: AuthServiceDep, session_token: SessionCookie = None
) -> AuthenticatedUser | None:
    return await service.authenticate(session_token)


OptionalUserDep = Annotated[AuthenticatedUser | None, Depends(get_optional_user)]


async def get_current_user(user: OptionalUserDep) -> AuthenticatedUser:
    if user is None:
        raise NotAuthenticatedError()
    return user


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
