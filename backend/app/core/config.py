from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.enums import Region


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class BlizzardMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class Settings(BaseSettings):
    """Application settings, read from environment variables and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_name: str = "Forever Service Board"
    environment: Environment = Environment.DEVELOPMENT

    # Database
    database_url: str = "postgresql+asyncpg://forever:forever@localhost:5433/forever"

    # Web
    frontend_url: str = "http://localhost:3000"
    session_secret: SecretStr
    token_encryption_key: SecretStr

    # Blizzard / Battle.net. The Forever namespaces are unknown until launch (spec §13),
    # so they have no defaults and are only required in live mode.
    blizzard_mode: BlizzardMode = BlizzardMode.MOCK
    blizzard_client_id: str | None = None
    blizzard_client_secret: SecretStr | None = None
    blizzard_profile_namespace: str | None = None
    blizzard_static_namespace: str | None = None
    blizzard_regions: Annotated[list[Region], NoDecode] = Field(
        default_factory=lambda: list(Region)
    )
    oauth_redirect_url: str = "http://localhost:8000/api/auth/battlenet/callback"

    # Listings (spec §6.7)
    listing_lifetime_summon_minutes: int = Field(default=30, gt=0)
    listing_lifetime_portal_minutes: int = Field(default=30, gt=0)
    listing_lifetime_enchant_minutes: int = Field(default=24 * 60, gt=0)
    listing_lifetime_craft_minutes: int = Field(default=7 * 24 * 60, gt=0)
    inactive_character_days: int = Field(default=14, gt=0)

    # Exact whisper syntax for two-part names is unknown until launch (spec §13.4).
    whisper_format: str = (
        "/w {character_name} Hi! I saw your {service} listing on {site_name} ({price})."
    )

    @field_validator("blizzard_regions", mode="before")
    @classmethod
    def _split_regions(cls, value: object) -> object:
        """Accept a comma-separated string, e.g. `BLIZZARD_REGIONS=eu,us`."""
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _check_live_mode(self) -> "Settings":
        if self.blizzard_mode is BlizzardMode.LIVE:
            missing = [
                name
                for name in (
                    "blizzard_client_id",
                    "blizzard_client_secret",
                    "blizzard_profile_namespace",
                    "blizzard_static_namespace",
                )
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"BLIZZARD_MODE=live requires: {', '.join(missing).upper()}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
