from collections import defaultdict
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings
from app.core.enums import CharacterClass, Faction, Region, Ruleset
from app.integrations.blizzard.exceptions import (
    BlizzardAuthError,
    BlizzardCharacterNotFoundError,
)
from app.integrations.blizzard.mock import MockBlizzardProvider, load_seed_accounts
from app.integrations.blizzard.schemas import BlizzardToken

NOW = datetime(2026, 11, 5, 20, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def provider(settings: Settings, clock: Clock) -> MockBlizzardProvider:
    return MockBlizzardProvider(settings, now=clock)


def code_from(url: str) -> str:
    return parse_qs(urlsplit(url).query)["code"][0]


async def sign_in(
    provider: MockBlizzardProvider, account_key: str, region: Region
) -> BlizzardToken:
    return await provider.exchange_code(
        region, code_from(provider.authorize_url_for(account_key, "s"))
    )


def test_authorize_url_goes_straight_to_callback(provider: MockBlizzardProvider) -> None:
    url = urlsplit(provider.build_authorize_url(Region.EU, "state-1"))

    assert f"{url.scheme}://{url.netloc}{url.path}" == (
        "http://localhost:8000/api/auth/battlenet/callback"
    )
    assert parse_qs(url.query) == {"code": ["mock:eu-varek"], "state": ["state-1"]}


async def test_sign_in_flow(provider: MockBlizzardProvider) -> None:
    token = await sign_in(provider, "eu-lunara", Region.EU)

    account = await provider.fetch_account(token)
    characters = await provider.fetch_account_characters(token)

    assert token.expires_at == NOW + timedelta(hours=24)
    assert (account.account_id, account.battletag) == ("100002", "Lunara#4410")
    assert {c.full_name for c in characters} == {
        "Ilyra Windcrest",
        "Toruk Grimtusk",
        "Pell Ashdown",
        "Thessa Moonridge",
    }
    assert all(c.region is Region.EU for c in characters)


async def test_character_profile(provider: MockBlizzardProvider) -> None:
    token = await sign_in(provider, "eu-varek", Region.EU)
    characters = await provider.fetch_account_characters(token)
    morgath = next(c for c in characters if c.first_name == "Morgath")

    profile = await provider.fetch_character_profile(token, morgath)

    assert profile.full_name == "Morgath Ashveil"
    assert profile.character_class is CharacterClass.WARLOCK
    assert profile.faction is Faction.HORDE
    assert profile.ruleset is Ruleset.NORMAL
    assert profile.guild_name == "Ember Pact"
    assert profile.last_logout_at == NOW - timedelta(hours=1)


async def test_profile_of_character_on_another_account(provider: MockBlizzardProvider) -> None:
    varek = await sign_in(provider, "eu-varek", Region.EU)
    lunara = await sign_in(provider, "eu-lunara", Region.EU)
    lunara_character = (await provider.fetch_account_characters(lunara))[0]

    with pytest.raises(BlizzardCharacterNotFoundError):
        await provider.fetch_character_profile(varek, lunara_character)


@pytest.mark.parametrize(
    ("region", "code"),
    [
        (Region.EU, "mock:nobody"),
        (Region.EU, "eu-varek"),
        (Region.US, "mock:eu-varek"),
    ],
    ids=["unknown_account", "missing_prefix", "wrong_region"],
)
async def test_invalid_code(provider: MockBlizzardProvider, region: Region, code: str) -> None:
    with pytest.raises(BlizzardAuthError):
        await provider.exchange_code(region, code)


async def test_expired_token(provider: MockBlizzardProvider, clock: Clock) -> None:
    token = await sign_in(provider, "eu-varek", Region.EU)
    clock.now += timedelta(hours=24)

    with pytest.raises(BlizzardAuthError):
        await provider.fetch_account_characters(token)


# Seed data integrity: the mock must exercise the game rules from spec §4.


def test_seeds_cover_the_required_cases() -> None:
    characters = [(a, c) for a in load_seed_accounts() for c in a.characters]

    assert {a.region for a, _ in characters} >= {Region.EU, Region.US}
    assert {c.ruleset for _, c in characters} == set(Ruleset)
    assert {c.faction for _, c in characters if c.race == "Skyborne"} == set(Faction)
    assert {CharacterClass.WARLOCK, CharacterClass.MAGE} <= {
        c.character_class for _, c in characters
    }
    assert any(c.last_logout_hours_ago > 14 * 24 for _, c in characters), "an inactive character"


def test_seed_names_unique_per_region_and_ids_unique() -> None:
    characters = [(a, c) for a in load_seed_accounts() for c in a.characters]
    names = [(a.region, c.first_name, c.last_name) for a, c in characters]
    ids = [c.id for _, c in characters]

    assert len(names) == len(set(names))
    assert len(ids) == len(set(ids))


def test_seed_pvp_characters_one_faction_per_account() -> None:
    for account in load_seed_accounts():
        pvp_factions: defaultdict[Region, set[Faction]] = defaultdict(set)
        for character in account.characters:
            if character.ruleset is Ruleset.PVP:
                pvp_factions[account.region].add(character.faction)
        assert all(len(f) <= 1 for f in pvp_factions.values()), account.key
