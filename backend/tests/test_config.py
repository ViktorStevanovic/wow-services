import pytest
from pydantic import ValidationError

from app.core.config import BlizzardMode
from app.core.enums import Region
from tests.conftest import make_settings


def test_regions_accept_comma_separated_string() -> None:
    settings = make_settings(blizzard_regions="EU, us")

    assert settings.blizzard_regions == [Region.EU, Region.US]


def test_live_mode_requires_blizzard_credentials_and_namespaces() -> None:
    with pytest.raises(ValidationError, match="BLIZZARD_CLIENT_ID"):
        make_settings(blizzard_mode=BlizzardMode.LIVE)
