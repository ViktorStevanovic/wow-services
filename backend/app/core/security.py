"""Session tokens, encryption of stored Blizzard tokens, signed OAuth state, and cookies."""

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, SecretStr, ValidationError
from starlette.responses import Response

from app.core.config import Settings
from app.core.enums import Region

SESSION_COOKIE = "fsb_session"
OAUTH_STATE_COOKIE = "fsb_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/api/auth"
OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60


# --- Session tokens -------------------------------------------------------------------


def generate_token() -> str:
    """256 bits of randomness, URL-safe. Used for session tokens and OAuth state."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only the hash of a session token is stored, so a database leak can't hijack sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


# --- Encryption of stored Blizzard tokens ---------------------------------------------


class TokenCipher:
    """Symmetric encryption for secrets stored in the database.

    The Fernet key is derived from TOKEN_ENCRYPTION_KEY, so any high-entropy string works.
    """

    def __init__(self, key: SecretStr) -> None:
        digest = hashlib.sha256(key.get_secret_value().encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str | None:
        """None if the value was tampered with or encrypted with another key."""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            return None


# --- OAuth state ----------------------------------------------------------------------


class OAuthState(BaseModel):
    """What we remember between the login redirect and the Battle.net callback."""

    state: str
    region: Region


class OAuthStateSigner:
    """Signs the OAuth state into a short-lived cookie, so no server-side storage is needed."""

    def __init__(self, secret: SecretStr) -> None:
        self._serializer = URLSafeTimedSerializer(secret.get_secret_value(), salt="oauth-state")

    def dumps(self, value: OAuthState) -> str:
        return self._serializer.dumps(value.model_dump(mode="json"))

    def loads(self, signed: str) -> OAuthState | None:
        """None if the cookie is tampered with, malformed, or older than 10 minutes."""
        try:
            data = self._serializer.loads(signed, max_age=OAUTH_STATE_MAX_AGE_SECONDS)
            return OAuthState.model_validate(data)
        except (BadSignature, ValidationError):
            return None


# --- Cookies --------------------------------------------------------------------------


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_lifetime_days * 24 * 3600,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


def set_oauth_state_cookie(response: Response, signed_state: str, settings: Settings) -> None:
    # SameSite=Lax still sends it on the top-level redirect back from Battle.net.
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        signed_state,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        path=OAUTH_STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_oauth_state_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        OAUTH_STATE_COOKIE,
        path=OAUTH_STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
