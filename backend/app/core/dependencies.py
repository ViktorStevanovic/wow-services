from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.db import SessionDep

__all__ = ["SessionDep", "SettingsDep"]


def get_app_settings(request: Request) -> Settings:
    """The settings the running app was created with (overridable in tests)."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
