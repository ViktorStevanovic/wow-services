"""polyfactory setup. Feature factories subclass `BaseFactory`:

    class ListingFactory(BaseFactory[Listing]):
        ...

    listing = await ListingFactory.create_async(price_copper=20_000)

The `_bind_factories` fixture points every factory at the test's rolled-back session.
"""

from typing import Any

from polyfactory.factories.sqlalchemy_factory import (
    SQLAlchemyFactory,
    SQLAlchemyPersistenceMethod,
)
from sqlalchemy import Column


class BaseFactory[T](SQLAlchemyFactory[T]):
    __is_base_factory__ = True
    __set_relationships__ = False
    # The test session is rolled back anyway; flushing is enough for the row to be visible.
    __persistence_method__ = SQLAlchemyPersistenceMethod.FLUSH

    @classmethod
    def should_column_be_set(cls, column: Any) -> bool:
        # Leave server-generated values (created_at, updated_at...) to the database.
        if isinstance(column, Column) and column.server_default is not None:
            return False
        return super().should_column_be_set(column)
