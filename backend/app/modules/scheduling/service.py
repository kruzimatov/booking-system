import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.timezone import local_today
from app.modules.bookings.models import Booking
from app.modules.bookings.repository import BookingRepository
from app.modules.catalog.repository import CatalogRepository
from app.modules.providers.models import Provider
from app.modules.providers.repository import ProviderRepository
from app.modules.scheduling.day import load_provider_day, schedule_rules, search_range
from app.modules.scheduling.domain import TimeRange, compute_slots, fits_weekly_hours
from app.modules.scheduling.models import AvailabilityWindow, TimeOff
from app.modules.scheduling.repository import ScheduleRepository
from app.modules.scheduling.schemas import TimeOffCreate, WindowIn


def schedule_conflict(bookings: list[Booking], change: str) -> ConflictError:
    # Never orphan a client's booking silently: the admin must cancel or move it first.
    return ConflictError(
        f"{len(bookings)} active booking(s) conflict with {change}. Cancel them first.",
        code="SCHEDULE_CONFLICT",
        details={"booking_ids": [str(booking.id) for booking in bookings]},
    )


class ScheduleService:
    def __init__(self, db: Session, clock: Clock, settings: Settings) -> None:
        self.db = db
        self.clock = clock
        self.rules = schedule_rules(settings)
        self.schedule = ScheduleRepository(db)
        self.providers = ProviderRepository(db)
        self.catalog = CatalogRepository(db)
        self.bookings = BookingRepository(db)

    def get_availability(self, provider_id: uuid.UUID) -> list[AvailabilityWindow]:
        self._active_provider(provider_id)
        return self.schedule.windows(provider_id)

    def replace_availability(
        self, provider_id: uuid.UUID, windows: list[WindowIn]
    ) -> list[AvailabilityWindow]:
        self._locked_provider(provider_id)
        weekly = [(window.weekday, window.start_time, window.end_time) for window in windows]
        orphaned = [
            booking
            for booking in self.bookings.future_active_for_provider(provider_id, self.clock.now())
            if not fits_weekly_hours(
                TimeRange(booking.starts_at, booking.ends_at), weekly, self.rules.tz
            )
        ]
        if orphaned:
            raise schedule_conflict(orphaned, "the new working hours")
        self.schedule.replace_windows(
            provider_id,
            (
                AvailabilityWindow(
                    provider_id=provider_id,
                    weekday=window.weekday,
                    start_time=window.start_time,
                    end_time=window.end_time,
                )
                for window in windows
            ),
        )
        self.db.commit()
        return self.schedule.windows(provider_id)

    def list_time_off(self, provider_id: uuid.UUID) -> list[TimeOff]:
        self._provider(provider_id)
        return self.schedule.upcoming_time_off(provider_id, self.clock.now())

    def add_time_off(self, provider_id: uuid.UUID, data: TimeOffCreate) -> TimeOff:
        self._locked_provider(provider_id)
        if data.ends_at <= self.clock.now():
            raise UnprocessableError("Time off must end in the future.", code="TIME_OFF_IN_PAST")
        overlapping = self.bookings.active_for_provider_between(
            provider_id, data.starts_at, data.ends_at
        )
        if overlapping:
            raise schedule_conflict(overlapping, "this time off")
        time_off = TimeOff(
            provider_id=provider_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            reason=data.reason,
        )
        self.schedule.add_time_off(time_off)
        self.db.commit()
        return time_off

    def delete_time_off(self, provider_id: uuid.UUID, time_off_id: uuid.UUID) -> None:
        self._locked_provider(provider_id)
        time_off = self.schedule.get_time_off(provider_id, time_off_id)
        if time_off is None:
            raise NotFoundError("Time off not found.")
        self.schedule.delete_time_off(time_off)
        self.db.commit()

    def get_slots(
        self, provider_id: uuid.UUID, service_id: uuid.UUID, day: date
    ) -> list[TimeRange]:
        provider = self._active_provider(provider_id)
        service = self.catalog.get(service_id)
        if service is None or not service.is_active:
            raise NotFoundError("Service not found.")
        if service.id not in provider.service_ids:
            raise UnprocessableError(
                "This provider does not offer this service.", code="SERVICE_NOT_OFFERED"
            )
        now = self.clock.now()
        today = local_today(now, self.rules.tz)
        if not today <= day <= today + timedelta(days=self.rules.max_advance_days):
            raise UnprocessableError(
                f"Choose a date from today up to {self.rules.max_advance_days} days ahead.",
                code="DATE_OUT_OF_RANGE",
            )
        around = search_range(day, self.rules)
        busy = self.bookings.busy_ranges(provider_id, around.start, around.end)
        provider_day = load_provider_day(self.schedule, provider_id, day, self.rules, busy)
        return compute_slots(
            duration=timedelta(minutes=service.duration_minutes),
            buffer=timedelta(minutes=service.buffer_minutes),
            day=provider_day,
            rules=self.rules,
            now=now,
        )

    def _provider(self, provider_id: uuid.UUID) -> Provider:
        provider = self.providers.get(provider_id)
        if provider is None:
            raise NotFoundError("Provider not found.")
        return provider

    def _active_provider(self, provider_id: uuid.UUID) -> Provider:
        provider = self.providers.get(provider_id)
        if provider is None or not provider.is_active:
            raise NotFoundError("Provider not found.")
        return provider

    def _locked_provider(self, provider_id: uuid.UUID) -> Provider:
        provider = self.providers.lock(provider_id)
        if provider is None:
            raise NotFoundError("Provider not found.")
        return provider
