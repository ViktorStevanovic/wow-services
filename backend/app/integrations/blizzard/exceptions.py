from app.core.errors import NotAuthenticatedError, NotFoundError, UpstreamServiceError


class BlizzardAuthError(NotAuthenticatedError):
    """The authorization code or access token was rejected (invalid, used, or expired)."""

    code = "blizzard_auth_failed"
    message = "Battle.net sign-in failed or expired. Please sign in again."


class BlizzardCharacterNotFoundError(NotFoundError):
    """The character is not (or no longer) on the token's account."""

    code = "blizzard_character_not_found"
    message = "This character was not found on your Battle.net account."


class BlizzardUnavailableError(UpstreamServiceError):
    """Blizzard is down, timing out, or still rate limiting us after retries."""

    code = "blizzard_unavailable"
    message = "Battle.net is not responding. Try again in a moment."


class BlizzardNotSupportedError(UpstreamServiceError):
    """The live API can't do this yet (the Forever API is not published, spec §13)."""

    code = "blizzard_not_supported"
    message = "This Battle.net feature is not available yet."
