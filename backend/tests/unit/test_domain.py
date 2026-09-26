from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.timezone import local_day_bounds, local_today
from app.modules.scheduling.domain import (
    ProviderDay,
    ScheduleRules,
    SlotRejection,
    TimeRange,
    check_start,
    compute_slots,
    windows_for_date,
)

TZ = ZoneInfo("Asia/Tashkent")
MONDAY = date(2030, 1, 7)
RULES = ScheduleRules(
    tz=TZ, step=timedelta(minutes=15), min_notice=timedelta(minutes=60), max_advance_days=60
)
HOUR = timedelta(hours=1)
NO_BUFFER = timedelta(0)


def at(hour: int, minute: int = 0, second: int = 0, day: date = MONDAY) -> datetime:
    """Tashkent wall-clock time on the given day, as UTC."""
    return datetime.combine(day, time(hour, minute, second), tzinfo=TZ).astimezone(UTC)


def span(start: tuple[int, int], end: tuple[int, int]) -> TimeRange:
    return TimeRange(at(*start), at(*end))


def provider_day(
    windows: tuple[tuple[int, int], ...] = ((9, 13), (14, 18)),
    time_off: tuple[TimeRange, ...] = (),
    busy: tuple[TimeRange, ...] = (),
) -> ProviderDay:
    local = [(time(start), time(end)) for start, end in windows]
    return ProviderDay(windows=windows_for_date(local, MONDAY, TZ), time_off=time_off, busy=busy)


def check(
    start: datetime, day: ProviderDay, now: datetime | None = None, buffer: timedelta = NO_BUFFER
) -> SlotRejection | None:
    return check_start(start, duration=HOUR, buffer=buffer, day=day, rules=RULES, now=now or at(6))


def local_starts(slots: list[TimeRange]) -> list[str]:
    return [slot.start.astimezone(TZ).strftime("%H:%M") for slot in slots]


def quarter_hours(first: str, last: str) -> list[str]:
    start = datetime.strptime(first, "%H:%M")
    end = datetime.strptime(last, "%H:%M")
    times = []
    while start <= end:
        times.append(start.strftime("%H:%M"))
        start += timedelta(minutes=15)
    return times


def test_lunch_break_splits_the_day_and_last_slot_ends_at_closing() -> None:
    slots = compute_slots(
        duration=HOUR, buffer=NO_BUFFER, day=provider_day(), rules=RULES, now=at(6)
    )

    assert local_starts(slots) == quarter_hours("09:00", "12:00") + quarter_hours("14:00", "17:00")


def test_back_to_back_bookings_are_allowed() -> None:
    day = provider_day(busy=(span((10, 0), (11, 0)),))

    assert check(at(9), day) is None
    assert check(at(11), day) is None


def test_partial_overlap_is_taken() -> None:
    day = provider_day(busy=(span((10, 0), (11, 0)),))

    assert check(at(10, 30), day) is SlotRejection.TAKEN
    assert check(at(9, 30), day) is SlotRejection.TAKEN


def test_existing_buffer_blocks_the_next_start() -> None:
    day = provider_day(busy=(span((10, 0), (11, 15)),))

    assert check(at(11), day) is SlotRejection.TAKEN
    assert check(at(11, 15), day) is None


def test_own_buffer_may_run_past_closing_but_not_into_the_next_booking() -> None:
    assert check(at(17), provider_day(), buffer=timedelta(minutes=15)) is None
    day = provider_day(busy=(span((11, 0), (12, 0)),))
    assert check(at(10), day, buffer=timedelta(minutes=15)) is SlotRejection.TAKEN


def test_time_off_removes_overlapping_slots() -> None:
    day = provider_day(time_off=(span((12, 0), (15, 0)),))
    slots = compute_slots(duration=HOUR, buffer=NO_BUFFER, day=day, rules=RULES, now=at(6))

    assert check(at(11, 30), day) is SlotRejection.PROVIDER_UNAVAILABLE
    assert local_starts(slots) == quarter_hours("09:00", "11:00") + quarter_hours("15:00", "17:00")


def test_minimum_notice_from_now() -> None:
    day = provider_day()
    slots = compute_slots(duration=HOUR, buffer=NO_BUFFER, day=day, rules=RULES, now=at(9, 20))

    assert local_starts(slots)[0] == "10:30"
    assert check(at(10, 15), day, now=at(9, 20)) is SlotRejection.TOO_SOON


def test_start_in_the_past_is_too_soon() -> None:
    assert check(at(9), provider_day(), now=at(15)) is SlotRejection.TOO_SOON


def test_booking_window_ends_after_max_advance_days() -> None:
    last_day = MONDAY + timedelta(days=60)

    assert check(at(10, day=last_day + timedelta(days=1)), provider_day()) is SlotRejection.TOO_FAR
    assert check(at(10, day=last_day), provider_day()) is SlotRejection.OUTSIDE_HOURS


def test_off_grid_starts_are_rejected_first() -> None:
    day = provider_day(busy=(span((9, 0), (10, 0)),))

    assert check(at(9, 10), day) is SlotRejection.OFF_GRID
    assert check(at(9, 0, 30), day) is SlotRejection.OFF_GRID


def test_outside_working_hours_and_during_lunch() -> None:
    day = provider_day()

    assert check(at(8), day) is SlotRejection.OUTSIDE_HOURS
    assert check(at(12, 30), day) is SlotRejection.OUTSIDE_HOURS
    assert check(at(17, 15), day) is SlotRejection.OUTSIDE_HOURS


def test_day_without_windows_has_no_slots() -> None:
    day = provider_day(windows=())

    assert compute_slots(duration=HOUR, buffer=NO_BUFFER, day=day, rules=RULES, now=at(6)) == []


def test_touching_windows_are_merged() -> None:
    day = provider_day(windows=((9, 13), (13, 18)))

    assert len(day.windows) == 1
    assert check(at(12, 30), day) is None


def test_business_today_rolls_over_before_utc_midnight() -> None:
    evening_utc = datetime(2030, 1, 7, 20, 0, tzinfo=UTC)

    assert local_today(evening_utc, TZ) == date(2030, 1, 8)
    start, end = local_day_bounds(date(2030, 1, 8), TZ)
    assert start == datetime(2030, 1, 7, 19, 0, tzinfo=UTC)
    assert end - start == timedelta(days=1)
