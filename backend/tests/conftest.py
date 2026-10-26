import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://forever:forever@localhost:5434/forever_test",
)


def make_settings(**overrides: object) -> Settings:
    """Test settings that ignore the developer's `.env` file."""
    values: dict[str, object] = {
        "environment": Environment.TEST,
        "database_url": TEST_DATABASE_URL,
        "session_secret": SecretStr("test-session-secret"),
        "token_encryption_key": SecretStr("test-token-encryption-key"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]  # dynamic test overrides


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
