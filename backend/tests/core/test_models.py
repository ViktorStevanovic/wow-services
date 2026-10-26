"""The shared mixins on a throwaway table.

The `test_` prefix keeps it out of the models-vs-migrations check (tests/test_migrations.py),
and its table is created inside the rolled-back test transaction.
"""

import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.models import NAMING_CONVENTION, TimestampMixin, UUIDPrimaryKeyMixin
from tests.factories import BaseFactory


class MixinProbe(UUIDPrimaryKeyMixin, TimestampMixin, table=True):
    __tablename__ = "test_mixin_probe"
    __table_args__ = (UniqueConstraint("name"),)

    name: str = Field(index=True)


class MixinProbeFactory(BaseFactory[MixinProbe]):
    pass


async def create_probe_table(session: AsyncSession) -> None:
    connection = await session.connection()
    await connection.run_sync(MixinProbe.__table__.create)  # type: ignore[attr-defined]


def test_app_metadata_uses_naming_convention() -> None:
    assert SQLModel.metadata.naming_convention == NAMING_CONVENTION


def test_naming_convention_names_constraints_and_indexes() -> None:
    table = MixinProbe.__table__  # type: ignore[attr-defined]  # set by SQLModel at runtime

    assert table.primary_key.name == "pk_test_mixin_probe"
    assert {c.name for c in table.constraints if isinstance(c, UniqueConstraint)} == {
        "uq_test_mixin_probe_name"
    }
    assert {i.name for i in table.indexes} == {"ix_test_mixin_probe_name"}


async def test_mixins_generate_uuid_and_server_timestamps(db_session: AsyncSession) -> None:
    await create_probe_table(db_session)

    probe = await MixinProbeFactory.create_async(name="first")

    assert isinstance(probe.id, uuid.UUID)
    assert isinstance(probe.created_at, datetime)
    assert probe.created_at.tzinfo is not None
    assert probe.updated_at == probe.created_at


async def test_updated_at_is_loaded_after_update(db_session: AsyncSession) -> None:
    await create_probe_table(db_session)
    probe = await MixinProbeFactory.create_async(name="before")

    probe.name = "after"
    await db_session.commit()

    # Eager defaults: reading the refreshed value needs no lazy load (which would fail).
    assert probe.updated_at.tzinfo is not None
