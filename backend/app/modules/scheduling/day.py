"""Builds the inputs of the pure slot engine from the database. Shared by slots and bookings."""

import uuid
from collections.abc import Iterable
from datetime import date, timedelta

from app.core.config import Settings
from app.core.timezone import local_day_bounds
from app.modules.catalog.models import DURATION_STEP_MINUTES
from app.modules.scheduling.domain import ProviderDay, ScheduleRules, TimeRange, windows_for_date
from app.modules.scheduling.repository import ScheduleRepository


def schedule_rules(settings: Settings) -> ScheduleRules:
    return ScheduleRules(
        tz=settings.business_tz,
        step=timedelta(minutes=DURATION_STEP_MINUTES),
        min_notice=timedelta(minutes=settings.min_notice_minutes),
        max_advance_days=settings.max_advance_days,
    )


def search_range(day: date, rules: ScheduleRules) -> TimeRange:
    """The local day widened by a day on each side, so buffers crossing midnight are seen."""
    start, end = local_day_bounds(day, rules.tz)
    return TimeRange(start - timedelta(days=1), end + timedelta(days=1))


def load_provider_day(
    schedule: ScheduleRepository,
    provider_id: uuid.UUID,
    day: date,
    rules: ScheduleRules,
    busy: Iterable[TimeRange] = (),
) -> ProviderDay:
    weekly = schedule.windows(provider_id, weekday=day.weekday())
    around = search_range(day, rules)
    time_off = schedule.time_off_between(provider_id, around.start, around.end)
    return ProviderDay(
        windows=windows_for_date(((w.start_time, w.end_time) for w in weekly), day, rules.tz),
        time_off=tuple(TimeRange(off.starts_at, off.ends_at) for off in time_off),
        busy=tuple(busy),
    )
