"""What the Blizzard provider returns, independent of Blizzard's raw JSON.

Internal DTOs: never sent to the browser as-is (the access token in particular).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.core.enums import CharacterClass, Faction, Region, Ruleset


class _ProviderModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class BlizzardToken(_ProviderModel):
    """A user access token. Blizzard user tokens last 24 h and cannot be refreshed (spec §7.2)."""

    access_token: SecretStr
    region: Region
    expires_at: datetime


class BlizzardAccount(_ProviderModel):
    """The Battle.net account behind a token."""

    account_id: str = Field(min_length=1)
    battletag: str | None = None


class AccountCharacter(_ProviderModel):
    """One Forever character from the account's character list."""

    blizzard_character_id: int
    region: Region
    ruleset: Ruleset
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    faction: Faction
    race: str = Field(min_length=1)
    character_class: CharacterClass
    level: int = Field(ge=1)
    # Opaque provider key used to fetch the full profile (the real URL slug is unknown, §13.3).
    profile_ref: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class CharacterProfile(AccountCharacter):
    """The account character plus profile-only fields."""

    guild_name: str | None = None
    # From `last_login_timestamp`, which reflects the last *logout* (spec §7.3).
    last_logout_at: datetime | None = None
