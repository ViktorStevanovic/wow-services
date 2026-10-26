import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Environment, Settings
from app.core.db import get_session
from app.main import create_app
from tests.factories import BaseFactory

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://forever:forever@localhost:5434/forever_test",
)


def make_settings(**overrides: object) -> Settings:
    """Test settings that ignore the developer's `.env` file."""
    values: dict[str, object] = {
        "environment": Environment.TEST,
        "database_url": TEST_DATABASE_URL,
        "session_secret": SecretStr("test-session-secret-0123456789abcdef"),
        "token_encryption_key": SecretStr("test-token-encryption-key-0123456789"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]  # dynamic test overrides


def alembic_config() -> Config:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    # alembic.ini's logging section would disable the app's loggers mid-run.
    config.attributes["skip_logging_config"] = True
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Bring the test database to the latest migration once per run."""
    command.upgrade(alembic_config(), "head")


@pytest.fixture(scope="session")
async def engine(migrated_database: None) -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(TEST_DATABASE_URL)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is rolled back after the test.

    `commit()` in services only releases a savepoint, so nothing leaks between tests.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture(autouse=True)
def _bind_factories(db_session: AsyncSession) -> Iterator[None]:
    BaseFactory.__async_session__ = db_session
    yield
    BaseFactory.__async_session__ = None


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@asynccontextmanager
async def running_app(settings: Settings, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    """The app with its lifespan running, using the test's rolled-back session."""
    application = create_app(settings)

    async def _test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = _test_session
    async with application.router.lifespan_context(application):
        yield application


def http_client(application: FastAPI, base_url: str = "http://test.local") -> AsyncClient:
    # raise_app_exceptions=False: let unhandled errors reach the app's 500 handling.
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url=base_url)


@pytest.fixture
async def app(settings: Settings, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    async with running_app(settings, db_session) as application:
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with http_client(app) as ac:
        yield ac
