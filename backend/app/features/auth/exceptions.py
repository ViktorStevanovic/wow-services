from app.core.errors import BusinessRuleError, NotAuthenticatedError, NotFoundError


class RegionNotSupportedError(BusinessRuleError):
    code = "region_not_supported"
    message = "Sign-in is not available for this region."


class OAuthStateError(NotAuthenticatedError):
    """Missing, expired, tampered or mismatched `state`: possible login CSRF."""

    code = "oauth_state_invalid"
    message = "The sign-in attempt expired or is invalid. Please try again."


class BattlenetLoginCancelledError(NotAuthenticatedError):
    code = "battlenet_login_cancelled"
    message = "Battle.net sign-in was cancelled."


class DevLoginUnavailableError(NotFoundError):
    """Dev login only exists in mock mode; elsewhere it behaves like a missing route."""

    code = "not_found"
    message = "Not found."


class DevAccountNotFoundError(NotFoundError):
    code = "dev_account_not_found"
    message = "No seeded account with this key."
