"""Imports every table model so SQLModel.metadata is complete (for Alembic and tests).

Add each feature's `models` module here when it gets one.
"""

import app.core.models  # applies the naming convention first
import app.features.auth.models
import app.features.users.models  # noqa: F401
