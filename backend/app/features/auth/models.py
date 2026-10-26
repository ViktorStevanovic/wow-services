import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, table=True):
    """A signed-in browser. The cookie holds a random token; only its hash is stored."""

    __tablename__ = "sessions"

    token_hash: str = Field(max_length=64, unique=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    # Kept only so characters can be re-imported while it's valid (24 h), then nulled.
    blizzard_token_encrypted: str | None = Field(default=None)
    blizzard_token_expires_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    expires_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)
