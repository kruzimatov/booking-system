"""Slot rules as pure functions: no database, no clock, no settings. Everything is passed in."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class TimeRange:
    """Half-open [start, end): 10:00-11:00 and 11:00-12:00 do not overlap."""

    start: datetime
    end: datetime

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "TimeRange") -> bool:
        return self.start <= other.start and other.end <= self.end


class SlotRejection(StrEnum):
    OFF_GRID = "SLOT_OFF_GRID"
    TOO_SOON = "SLOT_TOO_SOON"
    TOO_FAR = "SLOT_TOO_FAR"
    OUTSIDE_HOURS = "OUTSIDE_WORKING_HOURS"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TAKEN = "SLOT_TAKEN"


@dataclass(frozen=True, slots=True)
class ScheduleRules:
    tz: ZoneInfo
    step: timedelta
    min_notice: timedelta
    max_advance_days: int


@dataclass(frozen=True, slots=True)
class ProviderDay:
    windows: tuple[TimeRange, ...]
    time_off: tuple[TimeRange, ...]
    # Other active bookings as [starts_at, blocked_until): appointment plus cleanup buffer.
    busy: tuple[TimeRange, ...]


def merge_ranges(ranges: Iterable[TimeRange]) -> tuple[TimeRange, ...]:
    """Join touching or overlapping ranges, so 09-13 and 13-18 behave as one 09-18 window."""
    merged: list[TimeRange] = []
    for current in sorted(ranges, key=lambda item: item.start):
        if merged and current.start <= merged[-1].end:
            merged[-1] = TimeRange(merged[-1].start, max(merged[-1].end, current.end))
        else:
            merged.append(current)
    return tuple(merged)


def windows_for_date(
    local_windows: Iterable[tuple[time, time]], day: date, tz: ZoneInfo
) -> tuple[TimeRange, ...]:
    """Weekly local wall-clock windows placed on a concrete date, converted to UTC."""
    return merge_ranges(
        TimeRange(
            datetime.combine(day, start, tzinfo=tz).astimezone(UTC),
            datetime.combine(day, end, tzinfo=tz).astimezone(UTC),
        )
        for start, end in local_windows
    )


def is_on_grid(start: datetime, rules: ScheduleRules) -> bool:
    local = start.astimezone(rules.tz)
    minutes_since_midnight = local.hour * 60 + local.minute
    step_minutes = rules.step // timedelta(minutes=1)
    return (
        local.second == 0 and local.microsecond == 0 and minutes_since_midnight % step_minutes == 0
    )


def check_start(
    start: datetime,
    *,
    duration: timedelta,
    buffer: timedelta,
    day: ProviderDay,
    rules: ScheduleRules,
    now: datetime,
) -> SlotRejection | None:
    """Why this start time cannot be booked, or None if it can. The first failed check wins."""
    if not is_on_grid(start, rules):
        return SlotRejection.OFF_GRID
    if start < now + rules.min_notice:
        return SlotRejection.TOO_SOON
    last_bookable_day = now.astimezone(rules.tz).date() + timedelta(days=rules.max_advance_days)
    if start.astimezone(rules.tz).date() > last_bookable_day:
        return SlotRejection.TOO_FAR
    # The appointment must fit working hours; the buffer may run past closing time.
    appointment = TimeRange(start, start + duration)
    if not any(window.contains(appointment) for window in day.windows):
        return SlotRejection.OUTSIDE_HOURS
    blocked = TimeRange(start, start + duration + buffer)
    if any(blocked.overlaps(off) for off in day.time_off):
        return SlotRejection.PROVIDER_UNAVAILABLE
    if any(blocked.overlaps(booking) for booking in day.busy):
        return SlotRejection.TAKEN
    return None


def compute_slots(
    *,
    duration: timedelta,
    buffer: timedelta,
    day: ProviderDay,
    rules: ScheduleRules,
    now: datetime,
) -> list[TimeRange]:
    """Every bookable appointment range; uses check_start so listing and booking always agree."""
    slots: list[TimeRange] = []
    for window in day.windows:
        start = window.start
        while start + duration <= window.end:
            rejection = check_start(
                start, duration=duration, buffer=buffer, day=day, rules=rules, now=now
            )
            if rejection is None:
                slots.append(TimeRange(start, start + duration))
            start += rules.step
    return slots


def fits_weekly_hours(
    appointment: TimeRange, weekly: Iterable[tuple[int, time, time]], tz: ZoneInfo
) -> bool:
    """Whether an appointment still fits a weekly schedule of (weekday, start, end) rows."""
    day = appointment.start.astimezone(tz).date()
    same_weekday = [(start, end) for weekday, start, end in weekly if weekday == day.weekday()]
    return any(window.contains(appointment) for window in windows_for_date(same_weekday, day, tz))
