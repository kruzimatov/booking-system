"""create users table

Revision ID: cf40d53739ae
Revises:
Create Date: 2026-09-26 22:19:04.881841
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cf40d53739ae"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        # The role check is declared once below; create_constraint=False avoids a duplicate.
        sa.Column(
            "role",
            sa.Enum(
                "client",
                "admin",
                name="user_role",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            server_default="client",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint("role IN ('client', 'admin')", name=op.f("ck_users_user_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )


def downgrade() -> None:
    op.drop_table("users")
