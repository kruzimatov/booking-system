import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import ACTIVE_STATUSES, Booking, BookingEvent
from app.modules.scheduling.domain import TimeRange


class BookingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, booking_id: uuid.UUID) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def active_for_provider_between(
        self, provider_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[Booking]:
        # Same range as the provider exclusion constraint: [starts_at, blocked_until).
        query = (
            select(Booking)
            .where(Booking.provider_id == provider_id, Booking.status.in_(ACTIVE_STATUSES))
            .where(Booking.starts_at < end, Booking.blocked_until > start)
            .order_by(Booking.starts_at)
        )
        return list(self.db.scalars(query))

    def busy_ranges(
        self, provider_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[TimeRange]:
        return [
            TimeRange(booking.starts_at, booking.blocked_until)
            for booking in self.active_for_provider_between(provider_id, start, end)
        ]

    def future_active_for_provider(self, provider_id: uuid.UUID, now: datetime) -> list[Booking]:
        query = (
            select(Booking)
            .where(Booking.provider_id == provider_id, Booking.status.in_(ACTIVE_STATUSES))
            .where(Booking.ends_at > now)
            .order_by(Booking.starts_at)
        )
        return list(self.db.scalars(query))

    def count_active_future_for_client(self, client_id: uuid.UUID, now: datetime) -> int:
        query = (
            select(func.count())
            .select_from(Booking)
            .where(Booking.client_id == client_id, Booking.status.in_(ACTIVE_STATUSES))
            .where(Booking.ends_at > now)
        )
        return self.db.scalar(query) or 0

    def client_has_overlap(self, client_id: uuid.UUID, appointment: TimeRange) -> bool:
        # Same range as the client exclusion constraint: [starts_at, ends_at).
        query = (
            select(Booking.id)
            .where(Booking.client_id == client_id, Booking.status.in_(ACTIVE_STATUSES))
            .where(Booking.starts_at < appointment.end, Booking.ends_at > appointment.start)
            .limit(1)
        )
        return self.db.scalar(query) is not None

    def add(self, booking: Booking) -> None:
        self.db.add(booking)

    def add_event(self, event: BookingEvent) -> None:
        self.db.add(event)
