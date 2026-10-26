from typing import Annotated

from fastapi import Depends, Request

from app.core.config import BlizzardMode, Settings
from app.integrations.blizzard.live import LiveBlizzardProvider
from app.integrations.blizzard.mock import MockBlizzardProvider
from app.integrations.blizzard.provider import BlizzardProvider


def create_blizzard_provider(settings: Settings) -> BlizzardProvider:
    """The provider for BLIZZARD_MODE. Created once per process (in the app lifespan)."""
    match settings.blizzard_mode:
        case BlizzardMode.MOCK:
            return MockBlizzardProvider(settings)
        case BlizzardMode.LIVE:
            return LiveBlizzardProvider(settings)


def get_blizzard_provider(request: Request) -> BlizzardProvider:
    provider: BlizzardProvider = request.app.state.blizzard_provider
    return provider


BlizzardProviderDep = Annotated[BlizzardProvider, Depends(get_blizzard_provider)]
