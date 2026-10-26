from app.core.errors import ForbiddenError, NotFoundError


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "User not found."


class AccountSuspendedError(ForbiddenError):
    code = "account_suspended"
    message = "This account is suspended."
