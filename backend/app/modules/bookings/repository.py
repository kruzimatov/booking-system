import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import Select, and_, func, not_, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import ACTIVE_STATUSES, Booking, BookingEvent, BookingStatus
from app.modules.scheduling.domain import TimeRange

UPCOMING = "upcoming"


class BookingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, booking_id: uuid.UUID) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def lock(self, booking_id: uuid.UUID) -> Booking | None:
        # Status changes lock the booking row, so a client cancel and an admin confirm
        # at the same moment are applied one after the other, never both.
        query = select(Booking).where(Booking.id == booking_id).with_for_update()
        return self.db.scalar(query)

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

    def client_page(
        self, client_id: uuid.UUID, *, scope: str, now: datetime, page: int, size: int
    ) -> tuple[list[Booking], int]:
        upcoming = and_(Booking.status.in_(ACTIVE_STATUSES), Booking.ends_at > now)
        query = select(Booking).where(Booking.client_id == client_id)
        if scope == UPCOMING:
            query = query.where(upcoming).order_by(Booking.starts_at, Booking.id)
        else:
            query = query.where(not_(upcoming)).order_by(
                Booking.starts_at.desc(), Booking.id.desc()
            )
        return self._page(query, page, size)

    def admin_page(
        self,
        *,
        statuses: Collection[BookingStatus],
        provider_id: uuid.UUID | None,
        starts_from: datetime | None,
        starts_before: datetime | None,
        page: int,
        size: int,
    ) -> tuple[list[Booking], int]:
        query = select(Booking).order_by(Booking.starts_at, Booking.id)
        if statuses:
            query = query.where(Booking.status.in_(statuses))
        if provider_id is not None:
            query = query.where(Booking.provider_id == provider_id)
        if starts_from is not None:
            query = query.where(Booking.starts_at >= starts_from)
        if starts_before is not None:
            query = query.where(Booking.starts_at < starts_before)
        return self._page(query, page, size)

    def add(self, booking: Booking) -> None:
        self.db.add(booking)

    def add_event(self, event: BookingEvent) -> None:
        self.db.add(event)

    def _page(self, query: Select[Booking], page: int, size: int) -> tuple[list[Booking], int]:
        total = self.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        items = self.db.scalars(query.limit(size).offset((page - 1) * size))
        return list(items), total or 0
