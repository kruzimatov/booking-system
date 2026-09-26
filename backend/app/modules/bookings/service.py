import uuid
from collections.abc import Collection
from datetime import UTC, date, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableError,
    translate_integrity_errors,
)
from app.core.timezone import local_day_bounds
from app.modules.bookings.models import Booking, BookingEvent, BookingStatus
from app.modules.bookings.policies import (
    TRANSITIONS,
    Action,
    BookingFacts,
    Refusal,
    Viewer,
    allowed_actions,
    refusal,
)
from app.modules.bookings.repository import BookingRepository
from app.modules.bookings.schemas import BookingCreate
from app.modules.catalog.repository import CatalogRepository
from app.modules.providers.lookup import find_provider
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

REFUSAL_MESSAGES = {
    Refusal.INVALID_TRANSITION: "This booking can no longer change to that status.",
    Refusal.CANCEL_TOO_LATE: "It is too late to cancel online. Please contact the business.",
    Refusal.TOO_EARLY_TO_COMPLETE: "A booking can be completed only after it has ended.",
}


def rejection_error(rejection: SlotRejection) -> AppError:
    message = REJECTION_MESSAGES[rejection]
    if rejection is SlotRejection.TAKEN:
        return ConflictError(message, code=rejection.value)
    return UnprocessableError(message, code=rejection.value)


def _facts(booking: Booking) -> BookingFacts:
    return BookingFacts(status=booking.status, starts_at=booking.starts_at, ends_at=booking.ends_at)


def _viewer(user: User, booking: Booking) -> Viewer:
    return Viewer(is_admin=user.role is UserRole.ADMIN, is_owner=booking.client_id == user.id)


class BookingService:
    def __init__(self, db: Session, clock: Clock, settings: Settings) -> None:
        self.db = db
        self.clock = clock
        self.settings = settings
        self.rules = schedule_rules(settings)
        self.cancel_cutoff = timedelta(minutes=settings.cancel_cutoff_minutes)
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
        provider = find_provider(self.providers, data.provider_id, active_only=True, lock=True)
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
            self._record(booking, client, None)
            self.db.commit()
        return booking

    def apply(
        self, actor: User, booking_id: uuid.UUID, action: Action, reason: str | None = None
    ) -> Booking:
        booking = self.bookings.lock(booking_id)
        viewer = None if booking is None else _viewer(actor, booking)
        if booking is None or viewer is None or not (viewer.is_admin or viewer.is_owner):
            raise NotFoundError("Booking not found.")
        now = self.clock.now()
        refused = refusal(
            action, _facts(booking), viewer, now=now, cancel_cutoff=self.cancel_cutoff
        )
        if refused is Refusal.FORBIDDEN:
            raise ForbiddenError()
        if refused is not None:
            raise ConflictError(REFUSAL_MESSAGES[refused], code=refused.value)

        previous = booking.status
        booking.status = TRANSITIONS[action][1]
        if action is Action.CANCEL:
            booking.cancelled_at = now
            booking.cancel_reason = reason
        self._record(booking, actor, previous, reason)
        self.db.commit()
        # Reload so the response includes the event just recorded (events were loaded earlier).
        self.db.refresh(booking)
        return booking

    def get_own(self, client: User, booking_id: uuid.UUID) -> Booking:
        # Another client's booking is a 404, not a 403, so its existence is not revealed.
        booking = self.bookings.get(booking_id)
        if booking is None or booking.client_id != client.id:
            raise NotFoundError("Booking not found.")
        return booking

    def get_any(self, booking_id: uuid.UUID) -> Booking:
        booking = self.bookings.get(booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.")
        return booking

    def list_own(
        self, client: User, *, scope: str, page: int, size: int
    ) -> tuple[list[Booking], int]:
        return self.bookings.client_page(
            client.id, scope=scope, now=self.clock.now(), page=page, size=size
        )

    def list_all(
        self,
        *,
        statuses: Collection[BookingStatus],
        provider_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        page: int,
        size: int,
    ) -> tuple[list[Booking], int]:
        if date_from and date_to and date_from > date_to:
            raise UnprocessableError("date_from must not be after date_to.", code="INVALID_RANGE")
        # Dates are business-local calendar days; the range includes the whole of date_to.
        starts_from = local_day_bounds(date_from, self.rules.tz)[0] if date_from else None
        starts_before = local_day_bounds(date_to, self.rules.tz)[1] if date_to else None
        return self.bookings.admin_page(
            statuses=statuses,
            provider_id=provider_id,
            starts_from=starts_from,
            starts_before=starts_before,
            page=page,
            size=size,
        )

    def actions_for(self, viewer: User, booking: Booking) -> list[Action]:
        return allowed_actions(
            _facts(booking),
            _viewer(viewer, booking),
            now=self.clock.now(),
            cancel_cutoff=self.cancel_cutoff,
        )

    def _record(
        self,
        booking: Booking,
        actor: User,
        previous: BookingStatus | None,
        reason: str | None = None,
    ) -> None:
        self.bookings.add_event(
            BookingEvent(
                booking_id=booking.id,
                actor_id=actor.id,
                from_status=previous,
                to_status=booking.status,
                reason=reason,
            )
        )
