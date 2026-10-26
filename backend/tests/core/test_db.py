from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession


async def test_commits_in_tests_stay_inside_the_rolled_back_transaction(
    db_session: AsyncSession, engine: AsyncEngine
) -> None:
    await db_session.exec(text("CREATE TABLE isolation_probe (id int)"))  # type: ignore[call-overload]  # raw DDL
    await db_session.exec(text("INSERT INTO isolation_probe VALUES (1)"))  # type: ignore[call-overload]
    await db_session.commit()

    async with engine.connect() as other:
        visible = await other.scalar(text("SELECT to_regclass('isolation_probe')"))

    assert visible is None
