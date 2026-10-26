from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

import app.models_registry  # noqa: F401  # registers every table
from tests.conftest import alembic_config

TEST_TABLE_PREFIX = "test_"  # throwaway tables defined by tests, never migrated


def test_migrations_downgrade_and_upgrade_cleanly() -> None:
    config = alembic_config()

    command.downgrade(config, "base")
    command.upgrade(config, "head")


async def test_pg_trgm_extension_installed(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        installed = await connection.scalar(
            text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        )

    assert installed == 1


async def test_models_match_migrations(engine: AsyncEngine) -> None:
    """Fails when a model changed without a migration (or the other way round)."""

    def include_object(
        obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
    ) -> bool:
        return not (type_ == "table" and name and name.startswith(TEST_TABLE_PREFIX))

    def diff(connection: Connection) -> list[object]:
        context = MigrationContext.configure(connection, opts={"include_object": include_object})
        return list(compare_metadata(context, SQLModel.metadata))

    async with engine.connect() as connection:
        differences = await connection.run_sync(diff)

    assert differences == []
