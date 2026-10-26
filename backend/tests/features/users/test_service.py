import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import Region
from app.features.users.enums import UserStatus
from app.features.users.exceptions import UserNotFoundError
from app.features.users.models import User
from app.features.users.service import UserService
from app.integrations.blizzard.schemas import BlizzardAccount
from tests.features.users.factories import UserFactory

NOW = datetime(2026, 11, 5, 20, 0, tzinfo=UTC)


async def test_get_me(db_session: AsyncSession) -> None:
    user = await UserFactory.create_async(battletag="Ana#1234")

    me = await UserService(db_session).get_me(user.id)

    assert (me.id, me.battletag, me.status) == (user.id, "Ana#1234", UserStatus.ACTIVE)


async def test_get_me_unknown_user(db_session: AsyncSession) -> None:
    with pytest.raises(UserNotFoundError):
        await UserService(db_session).get_me(uuid.uuid4())


async def test_upsert_creates_user(db_session: AsyncSession) -> None:
    account = BlizzardAccount(account_id="42", battletag="Ana#1234")

    user = await UserService(db_session).upsert_from_battlenet(Region.EU, account, NOW)

    stored = await db_session.get(User, user.id)
    assert stored is not None
    assert (stored.battlenet_account_id, stored.region, stored.battletag) == (
        "42",
        Region.EU,
        "Ana#1234",
    )
    assert stored.status is UserStatus.ACTIVE
    assert stored.last_sign_in_at == NOW


async def test_upsert_updates_existing_user(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    first = await service.upsert_from_battlenet(Region.EU, BlizzardAccount(account_id="42"), NOW)
    later = NOW + timedelta(days=1)

    again = await service.upsert_from_battlenet(
        Region.EU, BlizzardAccount(account_id="42", battletag="Renamed#9"), later
    )

    stored = await db_session.get(User, first.id)
    assert again.id == first.id
    assert stored is not None
    assert (stored.battletag, stored.last_sign_in_at) == ("Renamed#9", later)


async def test_same_account_in_another_region_is_another_user(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    account = BlizzardAccount(account_id="42")

    eu = await service.upsert_from_battlenet(Region.EU, account, NOW)
    us = await service.upsert_from_battlenet(Region.US, account, NOW)

    assert eu.id != us.id
