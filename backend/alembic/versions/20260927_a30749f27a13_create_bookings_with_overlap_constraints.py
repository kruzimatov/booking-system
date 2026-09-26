"""create bookings with overlap constraints

Revision ID: a30749f27a13
Revises: f9c65b95945d
Create Date: 2026-09-27 00:06:16.043986

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a30749f27a13"
down_revision: str | Sequence[str] | None = "f9c65b95945d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Active = pending or confirmed. Only active bookings block time (see bookings/models.py).
ACTIVE = "status IN ('pending', 'confirmed')"


def upgrade() -> None:
    # btree_gist lets one GiST index combine "uuid =" with "range overlaps".
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "bookings",
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "cancelled",
                "completed",
                name="booking_status",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'completed')",
            name=op.f("ck_bookings_booking_status"),
        ),
        sa.CheckConstraint("blocked_until >= ends_at", name=op.f("ck_bookings_blocked_after_end")),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_bookings_time_order")),
        sa.CheckConstraint("price >= 0", name=op.f("ck_bookings_price_not_negative")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["users.id"],
            name=op.f("fk_bookings_client_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["providers.id"],
            name=op.f("fk_bookings_provider_id_providers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_bookings_service_id_services"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(
        "ix_bookings_client_starts", "bookings", ["client_id", "starts_at"], unique=False
    )
    op.create_index(
        "ix_bookings_provider_starts", "bookings", ["provider_id", "starts_at"], unique=False
    )
    op.create_index("ix_bookings_status_starts", "bookings", ["status", "starts_at"], unique=False)
    op.create_table(
        "booking_events",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_status",
            sa.Enum(
                "pending",
                "confirmed",
                "cancelled",
                "completed",
                name="booking_event_from_status",
                native_enum=False,
                length=16,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "pending",
                "confirmed",
                "cancelled",
                "completed",
                name="booking_event_to_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_booking_events_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_events_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_events")),
    )
    op.create_index(
        "ix_booking_events_booking", "booking_events", ["booking_id", "created_at"], unique=False
    )

    # The database itself refuses double bookings, even if application checks are bypassed.
    # Half-open ranges '[)': 10:00-11:00 and 11:00-12:00 do not collide.
    # A provider is busy until blocked_until (appointment plus cleanup buffer).
    op.execute(
        f"""
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_provider_overlap
        EXCLUDE USING gist (
            provider_id WITH =,
            tstzrange(starts_at, blocked_until, '[)') WITH &&
        ) WHERE ({ACTIVE})
        """
    )
    # A client cannot be in two appointments at once, with any providers.
    op.execute(
        f"""
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_client_overlap
        EXCLUDE USING gist (
            client_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE ({ACTIVE})
        """
    )


def downgrade() -> None:
    op.drop_index("ix_booking_events_booking", table_name="booking_events")
    op.drop_table("booking_events")
    op.drop_index("ix_bookings_status_starts", table_name="bookings")
    op.drop_index("ix_bookings_provider_starts", table_name="bookings")
    op.drop_index("ix_bookings_client_starts", table_name="bookings")
    op.drop_table("bookings")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
