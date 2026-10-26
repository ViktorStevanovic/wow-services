from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import RedirectResponse

from app.core.dependencies import SettingsDep
from app.core.enums import Region
from app.core.errors import error_responses
from app.core.security import (
    clear_oauth_state_cookie,
    clear_session_cookie,
    set_oauth_state_cookie,
    set_session_cookie,
)
from app.features.auth.dependencies import AuthServiceDep, OAuthStateCookie, SessionCookie
from app.features.auth.exceptions import (
    DevAccountNotFoundError,
    OAuthStateError,
    RegionNotSupportedError,
)
from app.features.auth.schemas import DevAccountRead, LoginRedirect
from app.features.users.exceptions import AccountSuspendedError
from app.integrations.blizzard.exceptions import BlizzardUnavailableError

router = APIRouter(prefix="/auth", tags=["auth"])


def _redirect_with_state(redirect: LoginRedirect, settings: SettingsDep) -> RedirectResponse:
    response = RedirectResponse(redirect.url, status_code=status.HTTP_302_FOUND)
    set_oauth_state_cookie(response, redirect.signed_state, settings)
    return response


@router.get(
    "/battlenet/login",
    response_class=RedirectResponse,
    response_model=None,
    status_code=status.HTTP_302_FOUND,
    summary="Start Battle.net sign-in",
    description=(
        "Redirects the browser to Battle.net for the chosen region. A short-lived signed "
        "cookie keeps the OAuth `state` until the callback. In mock mode the redirect goes "
        "straight to the callback as the region's first seeded account."
    ),
    responses={
        302: {"description": "Redirect to Battle.net."},
        **error_responses(RegionNotSupportedError, HTTPStatus.UNPROCESSABLE_ENTITY),
    },
)
async def battlenet_login(
    region: Annotated[Region, Query(description="Battle.net region to sign in to.")],
    service: AuthServiceDep,
    settings: SettingsDep,
) -> RedirectResponse:
    return _redirect_with_state(service.start_login(region), settings)


@router.get(
    "/battlenet/callback",
    response_class=RedirectResponse,
    response_model=None,
    status_code=status.HTTP_302_FOUND,
    summary="Battle.net sign-in callback",
    description=(
        "Battle.net redirects here after sign-in. Verifies `state`, exchanges the code, "
        "creates or updates the user, opens a session (httpOnly cookie) and redirects to "
        "the site. Not meant to be called by the frontend directly."
    ),
    responses={
        302: {"description": "Signed in; redirect to the site with the session cookie set."},
        **error_responses(OAuthStateError, AccountSuspendedError, BlizzardUnavailableError),
    },
)
async def battlenet_callback(
    service: AuthServiceDep,
    settings: SettingsDep,
    oauth_state: OAuthStateCookie = None,
    session_token: SessionCookie = None,
    code: Annotated[str | None, Query(max_length=512)] = None,
    state: Annotated[str | None, Query(max_length=256)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    result = await service.complete_login(
        signed_state=oauth_state,
        state=state,
        code=code,
        error=error,
        previous_session_token=session_token,
    )
    response = RedirectResponse(result.redirect_url, status_code=status.HTTP_302_FOUND)
    set_session_cookie(response, result.session_token, settings)
    clear_oauth_state_cookie(response, settings)
    return response


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out",
    description="Ends the current session and clears the cookie. Succeeds even if signed out.",
)
async def logout(
    service: AuthServiceDep,
    settings: SettingsDep,
    response: Response,
    session_token: SessionCookie = None,
) -> None:
    await service.logout(session_token)
    clear_session_cookie(response, settings)


@router.get(
    "/dev/accounts",
    response_model=list[DevAccountRead],
    status_code=status.HTTP_200_OK,
    summary="List mock accounts (mock mode only)",
    description=(
        "Seeded Battle.net accounts for the dev account picker. A fixed handful from "
        "`seeds/`, so not paginated. 404 unless `BLIZZARD_MODE=mock`."
    ),
    tags=["auth (mock mode)"],
    responses=error_responses(HTTPStatus.NOT_FOUND),
)
async def list_dev_accounts(service: AuthServiceDep) -> list[DevAccountRead]:
    return service.list_dev_accounts()


@router.get(
    "/dev/login",
    response_class=RedirectResponse,
    response_model=None,
    status_code=status.HTTP_302_FOUND,
    summary="Sign in as a mock account (mock mode only)",
    description="Runs the normal callback flow as the chosen seeded account. "
    "404 unless `BLIZZARD_MODE=mock`.",
    tags=["auth (mock mode)"],
    responses={
        302: {"description": "Redirect to the callback."},
        **error_responses(DevAccountNotFoundError, HTTPStatus.UNPROCESSABLE_ENTITY),
    },
)
async def dev_login(
    account: Annotated[str, Query(max_length=64, description="Seeded account key.")],
    service: AuthServiceDep,
    settings: SettingsDep,
) -> RedirectResponse:
    return _redirect_with_state(service.start_dev_login(account), settings)
