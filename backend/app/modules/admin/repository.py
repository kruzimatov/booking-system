import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingStatus
from app.modules.catalog.models import Service
from app.modules.providers.models import Provider


class StatsRepository:
    """Aggregate queries over bookings that start in [start, end)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def counts_by_status(self, start: datetime, end: datetime) -> dict[BookingStatus, int]:
        query = (
            select(Booking.status, func.count())
            .where(Booking.starts_at >= start, Booking.starts_at < end)
            .group_by(Booking.status)
        )
        return {status: count for status, count in self.db.execute(query).tuples()}

    def completed_revenue(self, start: datetime, end: datetime) -> Decimal:
        query = select(func.coalesce(func.sum(Booking.price), 0)).where(
            Booking.status == BookingStatus.COMPLETED,
            Booking.starts_at >= start,
            Booking.starts_at < end,
        )
        return Decimal(self.db.scalar(query) or 0)

    def bookings_per_provider(
        self, start: datetime, end: datetime
    ) -> list[tuple[uuid.UUID, str, int]]:
        # Cancelled bookings are left out: they are not work the provider did.
        query = (
            select(Provider.id, Provider.full_name, func.count(Booking.id))
            .join(Booking, Booking.provider_id == Provider.id)
            .where(Booking.starts_at >= start, Booking.starts_at < end)
            .where(Booking.status != BookingStatus.CANCELLED)
            .group_by(Provider.id, Provider.full_name)
            .order_by(func.count(Booking.id).desc(), Provider.full_name)
        )
        return list(self.db.execute(query).tuples())

    def top_services(
        self, start: datetime, end: datetime, limit: int
    ) -> list[tuple[uuid.UUID, str, int]]:
        query = (
            select(Service.id, Service.name, func.count(Booking.id))
            .join(Booking, Booking.service_id == Service.id)
            .where(Booking.starts_at >= start, Booking.starts_at < end)
            .where(Booking.status != BookingStatus.CANCELLED)
            .group_by(Service.id, Service.name)
            .order_by(func.count(Booking.id).desc(), Service.name)
            .limit(limit)
        )
        return list(self.db.execute(query).tuples())
