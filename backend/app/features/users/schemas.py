import uuid
from datetime import datetime

from app.core.enums import Region
from app.core.schemas import BaseSchema
from app.features.users.enums import UserStatus


class UserRead(BaseSchema):
    id: uuid.UUID
    region: Region
    status: UserStatus


class MeRead(BaseSchema):
    """The signed-in user's own account."""

    id: uuid.UUID
    region: Region
    battletag: str | None
    language: str | None
    status: UserStatus
    created_at: datetime
    last_sign_in_at: datetime
