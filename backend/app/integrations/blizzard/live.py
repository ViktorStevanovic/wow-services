"""Battle.net / Blizzard API client.

OAuth (authorize, token, userinfo) uses Blizzard's documented, region-independent endpoints.
The Forever *profile* API is not published yet (spec §7.1, §13): its namespace is config, and
the character calls raise `BlizzardNotSupportedError` until the response format is known.
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from pydantic import BaseModel, SecretStr, ValidationError

from app.core.config import Settings
from app.core.enums import Region
from app.integrations.blizzard.exceptions import (
    BlizzardAuthError,
    BlizzardNotSupportedError,
    BlizzardUnavailableError,
)
from app.integrations.blizzard.rate_limiter import RateLimiter, Sleep, blizzard_rate_limiter
from app.integrations.blizzard.schemas import (
    AccountCharacter,
    BlizzardAccount,
    BlizzardToken,
    CharacterProfile,
)

OAUTH_BASE_URL = "https://oauth.battle.net"
API_BASE_URL = "https://{region}.api.blizzard.com"
ACCOUNT_PROFILE_PATH = "/profile/user/wow"
SCOPE = "wow.profile"

TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_MAX_SECONDS = 8.0

logger = structlog.get_logger(__name__)


class _TokenResponse(BaseModel):
    access_token: str
    expires_in: int


class _UserInfoResponse(BaseModel):
    id: int
    battletag: str | None = None


class LiveBlizzardProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if settings.blizzard_client_id is None or settings.blizzard_client_secret is None:
            raise ValueError("LiveBlizzardProvider needs BLIZZARD_CLIENT_ID and _SECRET")
        self._settings = settings
        self._client_id = settings.blizzard_client_id
        self._client_secret = settings.blizzard_client_secret.get_secret_value()
        self._http = http_client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        self._limiter = rate_limiter or blizzard_rate_limiter()
        self._sleep = sleep

    def build_authorize_url(self, region: Region, state: str) -> str:
        # oauth.battle.net serves every region we support; `region` is kept with the state.
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._settings.oauth_redirect_url,
                "scope": SCOPE,
                "state": state,
            }
        )
        return f"{OAUTH_BASE_URL}/authorize?{query}"

    async def exchange_code(self, region: Region, code: str) -> BlizzardToken:
        response = await self._request(
            "POST",
            f"{OAUTH_BASE_URL}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.oauth_redirect_url,
            },
            auth=(self._client_id, self._client_secret),
        )
        if response.status_code in (400, 401):
            # invalid_grant: unknown, expired or already used code.
            raise BlizzardAuthError()
        self._raise_for_status(response)
        token = self._parse(response, _TokenResponse)
        return BlizzardToken(
            access_token=SecretStr(token.access_token),
            region=region,
            expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
        )

    async def fetch_account(self, token: BlizzardToken) -> BlizzardAccount:
        response = await self._request(
            "GET", f"{OAUTH_BASE_URL}/userinfo", headers=self._auth_header(token)
        )
        self._raise_for_status(response)
        info = self._parse(response, _UserInfoResponse)
        return BlizzardAccount(account_id=str(info.id), battletag=info.battletag)

    async def fetch_account_characters(self, token: BlizzardToken) -> list[AccountCharacter]:
        # Planned: GET {API_BASE_URL}{ACCOUNT_PROFILE_PATH}?namespace=<profile namespace>.
        # Not called yet: how Forever reports ruleset and two-part names is unknown (§13.2-3),
        # and guessing would import wrong data. Fails before using any API quota.
        raise BlizzardNotSupportedError(
            "Importing Forever characters is not available until Blizzard publishes the API.",
            details={"namespace": self._profile_namespace(token.region)},
        )

    async def fetch_character_profile(
        self, token: BlizzardToken, character: AccountCharacter
    ) -> CharacterProfile:
        # Planned: GET /profile/wow/character/{slug}/{name}; the Forever slug is unknown (§13.3).
        raise BlizzardNotSupportedError(
            "Character profiles are not available until Blizzard publishes the Forever API."
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _profile_namespace(self, region: Region) -> str:
        namespace = self._settings.blizzard_profile_namespace or ""
        return namespace.format(region=region.value)

    @staticmethod
    def _auth_header(token: BlizzardToken) -> dict[str, str]:
        return {"Authorization": f"Bearer {token.access_token.get_secret_value()}"}

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Throttled request, retried with backoff while Blizzard answers 429."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self._limiter.acquire()
            try:
                response = await self._http.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                logger.warning("blizzard.request_failed", url=url, error=type(exc).__name__)
                raise BlizzardUnavailableError() from exc
            if response.status_code != 429:
                return response
            if attempt == MAX_ATTEMPTS:
                break
            delay = self._retry_delay(response, attempt)
            logger.warning("blizzard.rate_limited", url=url, attempt=attempt, retry_in=delay)
            await self._sleep(delay)
        logger.error("blizzard.rate_limit_exhausted", url=url, attempts=MAX_ATTEMPTS)
        raise BlizzardUnavailableError()

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return min(float(retry_after), BACKOFF_MAX_SECONDS)
        backoff = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2.0 ** (attempt - 1))
        return backoff * random.uniform(0.5, 1.0)  # jitter so retries don't line up

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise BlizzardAuthError()
        if not response.is_success:
            logger.warning("blizzard.unexpected_status", status=response.status_code)
            raise BlizzardUnavailableError()

    @staticmethod
    def _parse[M: BaseModel](response: httpx.Response, model: type[M]) -> M:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            logger.error("blizzard.unexpected_response", model=model.__name__)
            raise BlizzardUnavailableError() from exc
