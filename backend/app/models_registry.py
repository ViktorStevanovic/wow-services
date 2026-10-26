"""Imports every table model so SQLModel.metadata is complete (for Alembic and tests).

Add each feature's `models` module here when it gets one.
"""

import app.core.models  # noqa: F401  # applies the naming convention first
