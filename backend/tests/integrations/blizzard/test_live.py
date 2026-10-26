from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import BlizzardMode, Settings
from app.core.enums import CharacterClass, Faction, Region, Ruleset
from app.integrations.blizzard.exceptions import (
    BlizzardAuthError,
    BlizzardNotSupportedError,
    BlizzardUnavailableError,
)
from app.integrations.blizzard.live import MAX_ATTEMPTS, LiveBlizzardProvider
from app.integrations.blizzard.rate_limiter import RateLimiter, TokenBucket
from app.integrations.blizzard.schemas import AccountCharacter, BlizzardToken
from tests.conftest import make_settings

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def live_settings() -> Settings:
    return make_settings(
        blizzard_mode=BlizzardMode.LIVE,
        blizzard_client_id="client-id",
        blizzard_client_secret=SecretStr("client-secret"),
        blizzard_profile_namespace="profile-forever-{region}",
        blizzard_static_namespace="static-forever-{region}",
    )


class Recorder:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def make_provider(settings: Settings, handler: Handler, recorder: Recorder) -> LiveBlizzardProvider:
    def record(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        return handler(request)

    return LiveBlizzardProvider(
        settings,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(record)),
        rate_limiter=RateLimiter([TokenBucket(rate=1_000, capacity=1_000)]),
        sleep=recorder.sleep,
    )


def token() -> BlizzardToken:
    return BlizzardToken(
        access_token=SecretStr("user-token"),
        region=Region.EU,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def test_authorize_url(live_settings: Settings) -> None:
    provider = make_provider(live_settings, lambda r: httpx.Response(500), Recorder())

    url = urlsplit(provider.build_authorize_url(Region.EU, "state-123"))

    assert (url.scheme, url.netloc, url.path) == ("https", "oauth.battle.net", "/authorize")
    assert parse_qs(url.query) == {
        "response_type": ["code"],
        "client_id": ["client-id"],
        "redirect_uri": ["http://localhost:8000/api/auth/battlenet/callback"],
        "scope": ["wow.profile"],
        "state": ["state-123"],
    }


async def test_exchange_code(live_settings: Settings) -> None:
    recorder = Recorder()
    provider = make_provider(
        live_settings,
        lambda r: httpx.Response(200, json={"access_token": "abc", "expires_in": 86_399}),
        recorder,
    )

    result = await provider.exchange_code(Region.EU, "the-code")

    assert result.access_token.get_secret_value() == "abc"
    assert result.region is Region.EU
    remaining = result.expires_at - datetime.now(UTC)
    assert timedelta(hours=23) < remaining <= timedelta(hours=24)
    [request] = recorder.requests
    assert str(request.url) == "https://oauth.battle.net/token"
    assert parse_qs(request.content.decode()) == {
        "grant_type": ["authorization_code"],
        "code": ["the-code"],
        "redirect_uri": ["http://localhost:8000/api/auth/battlenet/callback"],
    }
    assert request.headers["authorization"].startswith("Basic ")


async def test_exchange_code_rejected(live_settings: Settings) -> None:
    provider = make_provider(
        live_settings, lambda r: httpx.Response(400, json={"error": "invalid_grant"}), Recorder()
    )

    with pytest.raises(BlizzardAuthError):
        await provider.exchange_code(Region.EU, "used-code")


async def test_fetch_account(live_settings: Settings) -> None:
    recorder = Recorder()
    provider = make_provider(
        live_settings,
        lambda r: httpx.Response(200, json={"sub": "42", "id": 42, "battletag": "Ana#1234"}),
        recorder,
    )

    account = await provider.fetch_account(token())

    assert (account.account_id, account.battletag) == ("42", "Ana#1234")
    [request] = recorder.requests
    assert str(request.url) == "https://oauth.battle.net/userinfo"
    assert request.headers["authorization"] == "Bearer user-token"


async def test_expired_token_raises_auth_error(live_settings: Settings) -> None:
    provider = make_provider(live_settings, lambda r: httpx.Response(401), Recorder())

    with pytest.raises(BlizzardAuthError):
        await provider.fetch_account(token())


async def test_retries_429_with_retry_after_then_succeeds(live_settings: Settings) -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(429),
            httpx.Response(200, json={"id": 42}),
        ]
    )
    recorder = Recorder()
    provider = make_provider(live_settings, lambda r: next(responses), recorder)

    account = await provider.fetch_account(token())

    assert account.account_id == "42"
    assert len(recorder.requests) == 3
    assert recorder.sleeps[0] == 2.0
    assert 0.5 <= recorder.sleeps[1] <= 1.0  # backoff with jitter for attempt 2


async def test_gives_up_after_repeated_429(live_settings: Settings) -> None:
    recorder = Recorder()
    provider = make_provider(live_settings, lambda r: httpx.Response(429), recorder)

    with pytest.raises(BlizzardUnavailableError):
        await provider.fetch_account(token())

    assert len(recorder.requests) == MAX_ATTEMPTS
    assert len(recorder.sleeps) == MAX_ATTEMPTS - 1


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(503),
        lambda r: httpx.Response(200, json={"unexpected": True}),
        lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("timeout")),
    ],
    ids=["server_error", "malformed_body", "timeout"],
)
async def test_upstream_failures_raise_unavailable(
    live_settings: Settings, handler: Handler
) -> None:
    provider = make_provider(live_settings, handler, Recorder())

    with pytest.raises(BlizzardUnavailableError):
        await provider.fetch_account(token())


async def test_character_calls_not_supported_and_use_no_quota(live_settings: Settings) -> None:
    recorder = Recorder()
    provider = make_provider(live_settings, lambda r: httpx.Response(200), recorder)
    character = AccountCharacter(
        blizzard_character_id=1,
        region=Region.EU,
        ruleset=Ruleset.NORMAL,
        first_name="Ana",
        last_name="Stormcaller",
        faction=Faction.ALLIANCE,
        race="Human",
        character_class=CharacterClass.MAGE,
        level=60,
        profile_ref="1",
    )

    with pytest.raises(BlizzardNotSupportedError) as exc_info:
        await provider.fetch_account_characters(token())
    with pytest.raises(BlizzardNotSupportedError):
        await provider.fetch_character_profile(token(), character)

    assert exc_info.value.details == {"namespace": "profile-forever-eu"}
    assert recorder.requests == []


def test_requires_credentials() -> None:
    with pytest.raises(ValueError, match="BLIZZARD_CLIENT_ID"):
        LiveBlizzardProvider(make_settings())
