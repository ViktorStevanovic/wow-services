import uuid
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import Region
from app.features.users.exceptions import UserNotFoundError
from app.features.users.models import User
from app.features.users.schemas import MeRead, UserRead
from app.integrations.blizzard.schemas import BlizzardAccount


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_me(self, user_id: uuid.UUID) -> MeRead:
        user = await self._session.get(User, user_id)
        if user is None:
            raise UserNotFoundError()
        return MeRead.model_validate(user)

    async def upsert_from_battlenet(
        self, region: Region, account: BlizzardAccount, signed_in_at: datetime
    ) -> UserRead:
        """Create or update the user behind a Battle.net sign-in. Does not commit:
        the sign-in use case (auth) owns the transaction."""
        user = (
            await self._session.exec(
                select(User).where(
                    User.region == region,
                    User.battlenet_account_id == account.account_id,
                )
            )
        ).first()
        if user is None:
            user = User(
                battlenet_account_id=account.account_id,
                region=region,
                last_sign_in_at=signed_in_at,
            )
            self._session.add(user)
        user.battletag = account.battletag
        user.last_sign_in_at = signed_in_at
        await self._session.flush()
        return UserRead.model_validate(user)
