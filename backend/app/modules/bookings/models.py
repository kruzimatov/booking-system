import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKey
from app.modules.catalog.models import Service
from app.modules.providers.models import Provider
from app.modules.users.models import User


class BookingStatus(enum.StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# Only these block a slot; the exclusion constraints in the migration use the same list.
ACTIVE_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


def _status_type(name: str, *, with_check: bool) -> Enum:
    return Enum(
        BookingStatus,
        name=name,
        native_enum=False,
        create_constraint=with_check,
        length=16,
        values_callable=lambda statuses: [status.value for status in statuses],
    )


class Booking(UUIDPrimaryKey, TimestampMixin, Base):
    """Overlap rules live in the migration as EXCLUDE constraints (Alembic cannot model them)."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="time_order"),
        CheckConstraint("blocked_until >= ends_at", name="blocked_after_end"),
        CheckConstraint("price >= 0", name="price_not_negative"),
        Index("ix_bookings_client_starts", "client_id", "starts_at"),
        Index("ix_bookings_provider_starts", "provider_id", "starts_at"),
        Index("ix_bookings_status_starts", "status", "starts_at"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id", ondelete="RESTRICT"))
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # ends_at plus the service's cleanup buffer; the provider is busy until then.
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Copied from the service at booking time, so later price changes never rewrite history.
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[BookingStatus] = mapped_column(
        _status_type("booking_status", with_check=True),
        default=BookingStatus.PENDING,
        server_default=BookingStatus.PENDING.value,
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    client: Mapped[User] = relationship(lazy="selectin")
    provider: Mapped[Provider] = relationship(lazy="selectin")
    service: Mapped[Service] = relationship(lazy="selectin")
    events: Mapped[list["BookingEvent"]] = relationship(
        order_by="BookingEvent.created_at", lazy="selectin", viewonly=True
    )


class BookingEvent(UUIDPrimaryKey, Base):
    """Audit trail: one row per status change, including creation."""

    __tablename__ = "booking_events"
    __table_args__ = (Index("ix_booking_events_booking", "booking_id", "created_at"),)

    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    from_status: Mapped[BookingStatus | None] = mapped_column(
        _status_type("booking_event_from_status", with_check=False)
    )
    to_status: Mapped[BookingStatus] = mapped_column(
        _status_type("booking_event_to_status", with_check=False)
    )
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
