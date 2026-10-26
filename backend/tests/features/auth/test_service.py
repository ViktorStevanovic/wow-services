from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr
from sqlalchemy import func, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import BlizzardMode, Settings
from app.core.enums import Region
from app.core.security import TokenCipher, hash_token
from app.features.auth.exceptions import (
    BattlenetLoginCancelledError,
    DevAccountNotFoundError,
    DevLoginUnavailableError,
    OAuthStateError,
    RegionNotSupportedError,
)
from app.features.auth.models import UserSession
from app.features.auth.schemas import LoginRedirect, LoginResult
from app.features.auth.service import AuthService
from app.features.users.enums import UserStatus
from app.features.users.exceptions import AccountSuspendedError
from app.features.users.models import User
from app.features.users.service import UserService
from app.integrations.blizzard.exceptions import BlizzardAuthError
from app.integrations.blizzard.live import LiveBlizzardProvider
from app.integrations.blizzard.mock import MockBlizzardProvider
from tests.conftest import make_settings


def make_service(db_session: AsyncSession, settings: Settings) -> AuthService:
    return AuthService(
        db_session, settings, MockBlizzardProvider(settings), UserService(db_session)
    )


@pytest.fixture
def service(db_session: AsyncSession, settings: Settings) -> AuthService:
    return make_service(db_session, settings)


def query_of(redirect: LoginRedirect) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(redirect.url).query).items()}


async def login(
    service: AuthService, account: str = "eu-varek", **overrides: str | None
) -> LoginResult:
    redirect = service.start_dev_login(account)
    query = query_of(redirect)
    arguments: dict[str, str | None] = {
        "signed_state": redirect.signed_state,
        "state": query["state"],
        "code": query["code"],
        "error": None,
    }
    arguments.update(overrides)
    return await service.complete_login(**arguments)


async def stored_sessions(db_session: AsyncSession) -> list[UserSession]:
    return list((await db_session.exec(select(UserSession))).all())


# --- start_login ------------------------------------------------------------------------


def test_start_login(service: AuthService) -> None:
    redirect = service.start_login(Region.EU)

    query = query_of(redirect)
    assert query["code"] == "mock:eu-varek"  # mock: first seeded EU account
    assert len(query["state"]) >= 43
    assert redirect.signed_state  # opaque, verified on callback


def test_start_login_rejects_unsupported_region(db_session: AsyncSession) -> None:
    service = make_service(db_session, make_settings(blizzard_regions=[Region.US]))

    with pytest.raises(RegionNotSupportedError):
        service.start_login(Region.EU)


# --- complete_login ---------------------------------------------------------------------


async def test_complete_login_creates_user_and_session(
    service: AuthService, db_session: AsyncSession, settings: Settings
) -> None:
    result = await login(service, "eu-lunara")

    assert result.redirect_url == settings.frontend_url
    user = (await db_session.exec(select(User))).one()
    assert (user.battlenet_account_id, user.region, user.battletag) == (
        "100002",
        Region.EU,
        "Lunara#4410",
    )
    [session] = await stored_sessions(db_session)
    assert session.user_id == user.id
    assert session.token_hash == hash_token(result.session_token)
    assert session.blizzard_token_encrypted is not None
    cipher = TokenCipher(settings.token_encryption_key)
    assert cipher.decrypt(session.blizzard_token_encrypted) == "mock-token:eu-lunara"
    assert session.blizzard_token_expires_at is not None
    lifetime = session.expires_at - datetime.now(UTC)
    assert timedelta(days=29) < lifetime <= timedelta(days=30)


async def test_second_login_reuses_user(service: AuthService, db_session: AsyncSession) -> None:
    await login(service)
    await login(service)

    assert len((await db_session.exec(select(User))).all()) == 1
    assert len(await stored_sessions(db_session)) == 2


async def test_login_replaces_previous_session(
    service: AuthService, db_session: AsyncSession
) -> None:
    first = await login(service)

    second = await login(service, previous_session_token=first.session_token)

    [session] = await stored_sessions(db_session)
    assert session.token_hash == hash_token(second.session_token)


@pytest.mark.parametrize(
    "overrides",
    [
        {"signed_state": None},
        {"signed_state": "tampered"},
        {"state": None},
        {"state": "another-state"},
    ],
    ids=["missing_cookie", "tampered_cookie", "missing_state", "mismatched_state"],
)
async def test_invalid_state_is_rejected(
    service: AuthService, db_session: AsyncSession, overrides: dict[str, str | None]
) -> None:
    with pytest.raises(OAuthStateError):
        await login(service, "eu-varek", **overrides)

    assert await stored_sessions(db_session) == []


async def test_cancelled_on_battlenet(service: AuthService) -> None:
    with pytest.raises(BattlenetLoginCancelledError):
        await login(service, error="access_denied", code=None)


@pytest.mark.parametrize("code", [None, "mock:nobody"], ids=["missing", "unknown"])
async def test_bad_code(service: AuthService, code: str | None) -> None:
    with pytest.raises(BlizzardAuthError):
        await login(service, code=code)


async def test_suspended_user_cannot_sign_in(
    service: AuthService, db_session: AsyncSession
) -> None:
    await login(service)
    await db_session.exec(update(User).values(status=UserStatus.SUSPENDED))
    sessions_before = len(await stored_sessions(db_session))

    with pytest.raises(AccountSuspendedError):
        await login(service)

    assert len(await stored_sessions(db_session)) == sessions_before


# --- authenticate / logout --------------------------------------------------------------


async def test_authenticate(service: AuthService, db_session: AsyncSession) -> None:
    result = await login(service)

    user = await service.authenticate(result.session_token)

    assert user is not None
    stored = (await db_session.exec(select(User))).one()
    [session] = await stored_sessions(db_session)
    assert (user.id, user.region, user.session_id) == (stored.id, Region.EU, session.id)


@pytest.mark.parametrize("token", [None, "", "not-a-real-token"])
async def test_authenticate_without_valid_token(service: AuthService, token: str | None) -> None:
    await login(service)

    assert await service.authenticate(token) is None


async def test_authenticate_expired_session(service: AuthService, db_session: AsyncSession) -> None:
    result = await login(service)
    await db_session.exec(update(UserSession).values(expires_at=func.now() - timedelta(seconds=1)))

    assert await service.authenticate(result.session_token) is None


async def test_authenticate_suspended_user(service: AuthService, db_session: AsyncSession) -> None:
    result = await login(service)
    await db_session.exec(update(User).values(status=UserStatus.SUSPENDED))

    with pytest.raises(AccountSuspendedError):
        await service.authenticate(result.session_token)


async def test_logout_deletes_only_that_session(
    service: AuthService, db_session: AsyncSession
) -> None:
    first = await login(service)
    second = await login(service)

    await service.logout(first.session_token)

    remaining = await stored_sessions(db_session)
    assert [s.token_hash for s in remaining] == [hash_token(second.session_token)]


async def test_logout_without_session_is_a_no_op(service: AuthService) -> None:
    await service.logout(None)


# --- dev login --------------------------------------------------------------------------


def test_list_dev_accounts(service: AuthService) -> None:
    accounts = {a.key: a for a in service.list_dev_accounts()}

    assert set(accounts) == {"eu-varek", "eu-lunara", "us-dorin"}
    assert "Morgath Ashveil" in accounts["eu-varek"].character_names


async def test_dev_login_as_chosen_account(service: AuthService, db_session: AsyncSession) -> None:
    await login(service, "us-dorin")

    user = (await db_session.exec(select(User))).one()
    assert (user.region, user.battletag) == (Region.US, "Dorin#7788")


def test_dev_login_unknown_account(service: AuthService) -> None:
    with pytest.raises(DevAccountNotFoundError):
        service.start_dev_login("nobody")


async def test_dev_login_unavailable_in_live_mode(db_session: AsyncSession) -> None:
    settings = make_settings(
        blizzard_mode=BlizzardMode.LIVE,
        blizzard_client_id="id",
        blizzard_client_secret=SecretStr("secret"),
        blizzard_profile_namespace="p-{region}",
        blizzard_static_namespace="s-{region}",
    )
    provider = LiveBlizzardProvider(settings)
    service = AuthService(db_session, settings, provider, UserService(db_session))

    with pytest.raises(DevLoginUnavailableError):
        service.list_dev_accounts()
    with pytest.raises(DevLoginUnavailableError):
        service.start_dev_login("eu-varek")
    await provider.aclose()
