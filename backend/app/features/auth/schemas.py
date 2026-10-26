import uuid
from dataclasses import dataclass

from app.core.enums import Region
from app.core.schemas import BaseSchema
from app.features.users.enums import UserStatus


class AuthenticatedUser(BaseSchema):
    """The user behind the request's session cookie (what CurrentUserDep provides)."""

    id: uuid.UUID
    region: Region
    status: UserStatus
    session_id: uuid.UUID


class DevAccountRead(BaseSchema):
    """A seeded mock account for the dev-only account picker."""

    key: str
    region: Region
    battletag: str | None
    character_names: list[str]


@dataclass(frozen=True)
class LoginRedirect:
    """Where to send the browser, plus the signed state to keep in a cookie meanwhile."""

    url: str
    signed_state: str


@dataclass(frozen=True)
class LoginResult:
    """A completed sign-in: the new session token for the cookie, and where to go next."""

    session_token: str
    redirect_url: str
