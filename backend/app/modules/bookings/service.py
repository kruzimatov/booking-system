import uuid
from datetime import UTC, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    UnprocessableError,
    translate_integrity_errors,
)
from app.modules.bookings.models import Booking, BookingEvent, BookingStatus
from app.modules.bookings.repository import BookingRepository
from app.modules.bookings.schemas import BookingCreate
from app.modules.catalog.repository import CatalogRepository
from app.modules.providers.repository import ProviderRepository
from app.modules.scheduling.day import load_provider_day, schedule_rules, search_range
from app.modules.scheduling.domain import SlotRejection, TimeRange, check_start
from app.modules.scheduling.repository import ScheduleRepository
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

REJECTION_MESSAGES = {
    SlotRejection.OFF_GRID: "Bookings start on the 15-minute grid (e.g. 10:00, 10:15).",
    SlotRejection.TOO_SOON: "This time is in the past or too soon to book.",
    SlotRejection.TOO_FAR: "This time is too far ahead to book.",
    SlotRejection.OUTSIDE_HOURS: "The provider does not work at this time.",
    SlotRejection.PROVIDER_UNAVAILABLE: "The provider is not available at this time.",
    SlotRejection.TAKEN: "This time was just booked by someone else.",
}


def rejection_error(rejection: SlotRejection) -> AppError:
    message = REJECTION_MESSAGES[rejection]
    if rejection is SlotRejection.TAKEN:
        return ConflictError(message, code=rejection.value)
    return UnprocessableError(message, code=rejection.value)


class BookingService:
    def __init__(self, db: Session, clock: Clock, settings: Settings) -> None:
        self.db = db
        self.clock = clock
        self.settings = settings
        self.rules = schedule_rules(settings)
        self.bookings = BookingRepository(db)
        self.users = UserRepository(db)
        self.providers = ProviderRepository(db)
        self.catalog = CatalogRepository(db)
        self.schedule = ScheduleRepository(db)

    def create(self, client: User, data: BookingCreate) -> Booking:
        # Lock order everywhere: user -> provider -> booking. A fixed order cannot deadlock.
        # The user lock serializes one client's bookings (limit and self-overlap checks);
        # the provider lock serializes everything that changes that provider's schedule.
        self.users.lock(client.id)
        provider = self.providers.lock(data.provider_id)
        if provider is None or not provider.is_active:
            raise NotFoundError("Provider not found.")
        service = self.catalog.get(data.service_id)
        if service is None or not service.is_active:
            raise NotFoundError("Service not found.")
        if service.id not in provider.service_ids:
            raise UnprocessableError(
                "This provider does not offer this service.", code="SERVICE_NOT_OFFERED"
            )

        # Read after the locks: under READ COMMITTED this sees every booking committed before us.
        now = self.clock.now()
        starts_at = data.starts_at.astimezone(UTC)
        duration = timedelta(minutes=service.duration_minutes)
        buffer = timedelta(minutes=service.buffer_minutes)
        local_day = starts_at.astimezone(self.rules.tz).date()
        around = search_range(local_day, self.rules)
        busy = self.bookings.busy_ranges(provider.id, around.start, around.end)
        day = load_provider_day(self.schedule, provider.id, local_day, self.rules, busy)
        rejection = check_start(
            starts_at, duration=duration, buffer=buffer, day=day, rules=self.rules, now=now
        )
        if rejection is not None:
            raise rejection_error(rejection)

        appointment = TimeRange(starts_at, starts_at + duration)
        active = self.bookings.count_active_future_for_client(client.id, now)
        if active >= self.settings.max_active_bookings_per_client:
            raise ConflictError(
                f"You can have at most {self.settings.max_active_bookings_per_client} "
                "upcoming bookings.",
                code="ACTIVE_LIMIT_REACHED",
            )
        if self.bookings.client_has_overlap(client.id, appointment):
            raise ConflictError("You already have a booking at this time.", code="CLIENT_OVERLAP")

        booking = Booking(
            client_id=client.id,
            provider_id=provider.id,
            service_id=service.id,
            starts_at=appointment.start,
            ends_at=appointment.end,
            blocked_until=appointment.end + buffer,
            price=service.price,
            status=BookingStatus.PENDING,
            notes=data.notes,
        )
        self.bookings.add(booking)
        # The exclusion constraints are the last line of defense if anything above is bypassed.
        with translate_integrity_errors(self.db):
            self.db.flush()
            self.bookings.add_event(
                BookingEvent(
                    booking_id=booking.id,
                    actor_id=client.id,
                    from_status=None,
                    to_status=BookingStatus.PENDING,
                )
            )
            self.db.commit()
        return booking

    def get_visible(self, viewer: User, booking_id: uuid.UUID) -> Booking:
        # Another client's booking is a 404, not a 403, so its existence is not revealed.
        booking = self.bookings.get(booking_id)
        if booking is None or (
            viewer.role is not UserRole.ADMIN and booking.client_id != viewer.id
        ):
            raise NotFoundError("Booking not found.")
        return booking
