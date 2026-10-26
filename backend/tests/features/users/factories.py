from datetime import UTC, datetime

from polyfactory import Use

from app.core.enums import Region
from app.features.users.enums import UserStatus
from app.features.users.models import User
from tests.factories import BaseFactory


class UserFactory(BaseFactory[User]):
    battlenet_account_id = Use(lambda: str(BaseFactory.__faker__.unique.random_int(1, 10**9)))
    battletag = None
    region = Region.EU
    language = None
    status = UserStatus.ACTIVE
    last_sign_in_at = Use(lambda: datetime.now(UTC))
