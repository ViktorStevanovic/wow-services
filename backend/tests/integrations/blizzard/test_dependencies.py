from fastapi import FastAPI
from pydantic import SecretStr

from app.core.config import BlizzardMode
from app.integrations.blizzard.dependencies import create_blizzard_provider
from app.integrations.blizzard.live import LiveBlizzardProvider
from app.integrations.blizzard.mock import MockBlizzardProvider
from tests.conftest import make_settings


def test_mock_mode_creates_mock_provider() -> None:
    provider = create_blizzard_provider(make_settings(blizzard_mode=BlizzardMode.MOCK))

    assert isinstance(provider, MockBlizzardProvider)


async def test_live_mode_creates_live_provider() -> None:
    settings = make_settings(
        blizzard_mode=BlizzardMode.LIVE,
        blizzard_client_id="id",
        blizzard_client_secret=SecretStr("secret"),
        blizzard_profile_namespace="profile-forever-{region}",
        blizzard_static_namespace="static-forever-{region}",
    )

    provider = create_blizzard_provider(settings)

    assert isinstance(provider, LiveBlizzardProvider)
    await provider.aclose()


def test_app_uses_mock_provider_in_tests(app: FastAPI) -> None:
    assert isinstance(app.state.blizzard_provider, MockBlizzardProvider)
