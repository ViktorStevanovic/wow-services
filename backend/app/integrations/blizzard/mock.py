"""Battle.net stand-in reading `seeds/blizzard/accounts.json`, for BLIZZARD_MODE=mock and tests.

Sign-in skips Battle.net: the authorize URL points straight at our callback with a code that
names a seeded account (`mock:<account key>`).
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.core.config import Settings
from app.core.enums import CharacterClass, Faction, Region, Ruleset
from app.integrations.blizzard.exceptions import (
    BlizzardAuthError,
    BlizzardCharacterNotFoundError,
)
from app.integrations.blizzard.schemas import (
    AccountCharacter,
    BlizzardAccount,
    BlizzardToken,
    CharacterProfile,
)

SEED_FILE = Path(__file__).resolve().parents[3] / "seeds" / "blizzard" / "accounts.json"
CODE_PREFIX = "mock:"
TOKEN_PREFIX = "mock-token:"
TOKEN_LIFETIME = timedelta(hours=24)  # same as real Blizzard user tokens


class SeedCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: int
    first_name: str
    last_name: str
    ruleset: Ruleset
    faction: Faction
    race: str
    character_class: CharacterClass = Field(alias="class")
    level: int
    guild: str | None
    last_logout_hours_ago: float


class SeedAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    account_id: str
    battletag: str | None
    region: Region
    characters: list[SeedCharacter]


class SeedFile(BaseModel):
    accounts: list[SeedAccount]


def load_seed_accounts(path: Path = SEED_FILE) -> list[SeedAccount]:
    return SeedFile.model_validate_json(path.read_bytes()).accounts


class MockBlizzardProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        seed_path: Path = SEED_FILE,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._redirect_url = settings.oauth_redirect_url
        self._now = now
        self._accounts = {account.key: account for account in load_seed_accounts(seed_path)}

    @property
    def accounts(self) -> list[SeedAccount]:
        """Seeded accounts, e.g. for a dev-only account picker."""
        return list(self._accounts.values())

    def authorize_url_for(self, account_key: str, state: str) -> str:
        """Callback URL that signs in as one specific seeded account."""
        query = urlencode({"code": f"{CODE_PREFIX}{account_key}", "state": state})
        return f"{self._redirect_url}?{query}"

    def build_authorize_url(self, region: Region, state: str) -> str:
        """Signs in as the first seeded account of the region."""
        account = next((a for a in self._accounts.values() if a.region is region), None)
        return self.authorize_url_for(account.key if account else "unknown", state)

    async def exchange_code(self, region: Region, code: str) -> BlizzardToken:
        account = self._accounts.get(code.removeprefix(CODE_PREFIX))
        if not code.startswith(CODE_PREFIX) or account is None or account.region is not region:
            raise BlizzardAuthError()
        return BlizzardToken(
            access_token=SecretStr(f"{TOKEN_PREFIX}{account.key}"),
            region=region,
            expires_at=self._now() + TOKEN_LIFETIME,
        )

    async def fetch_account(self, token: BlizzardToken) -> BlizzardAccount:
        account = self._account_for(token)
        return BlizzardAccount(account_id=account.account_id, battletag=account.battletag)

    async def fetch_account_characters(self, token: BlizzardToken) -> list[AccountCharacter]:
        account = self._account_for(token)
        return [self._to_account_character(account, c) for c in account.characters]

    async def fetch_character_profile(
        self, token: BlizzardToken, character: AccountCharacter
    ) -> CharacterProfile:
        account = self._account_for(token)
        seed = next((c for c in account.characters if str(c.id) == character.profile_ref), None)
        if seed is None:
            raise BlizzardCharacterNotFoundError()
        return CharacterProfile(
            **self._to_account_character(account, seed).model_dump(),
            guild_name=seed.guild,
            last_logout_at=self._now() - timedelta(hours=seed.last_logout_hours_ago),
        )

    async def aclose(self) -> None:
        return None

    def _account_for(self, token: BlizzardToken) -> SeedAccount:
        key = token.access_token.get_secret_value().removeprefix(TOKEN_PREFIX)
        account = self._accounts.get(key)
        if account is None or token.expires_at <= self._now():
            raise BlizzardAuthError()
        return account

    @staticmethod
    def _to_account_character(account: SeedAccount, seed: SeedCharacter) -> AccountCharacter:
        return AccountCharacter(
            blizzard_character_id=seed.id,
            region=account.region,
            ruleset=seed.ruleset,
            first_name=seed.first_name,
            last_name=seed.last_name,
            faction=seed.faction,
            race=seed.race,
            character_class=seed.character_class,
            level=seed.level,
            profile_ref=str(seed.id),
        )
