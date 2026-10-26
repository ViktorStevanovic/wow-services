"""users and sessions

Users (one per Battle.net account and region) and server-side sessions (spec §9).

Revision ID: 01c762e2de40
Revises: 0001
Create Date: 2026-10-26 09:56:45.798820

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01c762e2de40"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("battlenet_account_id", sa.String(length=64), nullable=False),
        sa.Column("battletag", sa.String(length=64), nullable=True),
        sa.Column("region", sa.Enum("us", "eu", "kr", "tw", name="region"), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", name="user_status"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint(
            "region", "battlenet_account_id", name=op.f("uq_users_region_battlenet_account_id")
        ),
    )
    op.create_table(
        "sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("blizzard_token_encrypted", sa.String(), nullable=True),
        sa.Column("blizzard_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_expires_at"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
    # Autogenerate doesn't drop enum types; without this, upgrading again fails.
    sa.Enum(name="user_status").drop(op.get_bind())
    sa.Enum(name="region").drop(op.get_bind())
