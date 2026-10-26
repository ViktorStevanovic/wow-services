from typing import Protocol

from app.core.enums import Region
from app.integrations.blizzard.schemas import (
    AccountCharacter,
    BlizzardAccount,
    BlizzardToken,
    CharacterProfile,
)


class BlizzardProvider(Protocol):
    """Everything the app needs from Battle.net. Implemented by the live client and the mock.

    Errors: `BlizzardAuthError` for rejected codes/tokens, `BlizzardUnavailableError` for
    outages and exhausted retries, `BlizzardNotSupportedError` for calls the live API can't
    make yet.
    """

    def build_authorize_url(self, region: Region, state: str) -> str:
        """URL to send the browser to for sign-in. `state` comes back on the callback."""
        ...

    async def exchange_code(self, region: Region, code: str) -> BlizzardToken:
        """Trade the callback's authorization code for a user access token."""
        ...

    async def fetch_account(self, token: BlizzardToken) -> BlizzardAccount:
        """The Battle.net account (ID, BattleTag) that owns the token."""
        ...

    async def fetch_account_characters(self, token: BlizzardToken) -> list[AccountCharacter]:
        """The account's Forever characters in the token's region."""
        ...

    async def fetch_character_profile(
        self, token: BlizzardToken, character: AccountCharacter
    ) -> CharacterProfile:
        """Full profile of one character from `fetch_account_characters`."""
        ...

    async def aclose(self) -> None:
        """Release network resources."""
        ...
