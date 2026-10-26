from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field

from app.core.enums import Region
from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.features.users.enums import UserStatus


class User(UUIDPrimaryKeyMixin, TimestampMixin, table=True):
    __tablename__ = "users"
    # Battle.net account IDs are unique per region (spec §9).
    __table_args__ = (UniqueConstraint("region", "battlenet_account_id"),)

    battlenet_account_id: str = Field(max_length=64)
    # Collected but hidden by default (spec §11.3); only the user sees it for now.
    battletag: str | None = Field(default=None, max_length=64)
    region: Region = Field(sa_type=pg_enum(Region, "region"))
    language: str | None = Field(default=None, max_length=16)
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        sa_type=pg_enum(UserStatus, "user_status"),
        sa_column_kwargs={"server_default": UserStatus.ACTIVE.value},
    )
    last_sign_in_at: datetime = Field(sa_type=DateTime(timezone=True))
