import uuid
from datetime import UTC, datetime, timedelta

from app.modules.bookings.calendar import CalendarEvent, escape_text, fold, to_ics
from app.modules.bookings.models import BookingStatus

STARTS = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)  # 10:00 in Tashkent
BOOKING_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def event(**overrides: object) -> CalendarEvent:
    values: dict[str, object] = {
        "booking_id": BOOKING_ID,
        "service_name": "Haircut",
        "provider_name": "Temurbek Xolmatov",
        "starts_at": STARTS,
        "ends_at": STARTS + timedelta(minutes=45),
        "status": BookingStatus.CONFIRMED,
        "notes": None,
    }
    return CalendarEvent(**(values | overrides))  # type: ignore[arg-type]


def unfold(ics: str) -> list[str]:
    return ics.replace("\r\n ", "").split("\r\n")


def test_event_has_utc_times_stable_uid_and_crlf_lines() -> None:
    ics = to_ics(event(), generated_at=STARTS - timedelta(days=1))

    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    lines = unfold(ics)
    assert "DTSTART:20300107T050000Z" in lines
    assert "DTEND:20300107T054500Z" in lines
    assert "DTSTAMP:20300106T050000Z" in lines
    assert f"UID:{BOOKING_ID}@booking-system" in lines
    assert "SUMMARY:Haircut with Temurbek Xolmatov" in lines
    assert "STATUS:CONFIRMED" in lines


def test_pending_and_cancelled_map_to_calendar_statuses() -> None:
    pending = unfold(to_ics(event(status=BookingStatus.PENDING), generated_at=STARTS))
    cancelled = unfold(to_ics(event(status=BookingStatus.CANCELLED), generated_at=STARTS))

    assert "STATUS:TENTATIVE" in pending
    assert "STATUS:CANCELLED" in cancelled


def test_special_characters_are_escaped() -> None:
    assert (
        escape_text("Cut, wash; dry\\style\nthen tea") == "Cut\\, wash\\; dry\\\\style\\nthen tea"
    )
    ics = to_ics(event(notes="Short, please;\nno gel"), generated_at=STARTS)

    assert "DESCRIPTION:Status: confirmed\\nNotes: Short\\, please\\;\\nno gel" in unfold(ics)


def test_long_lines_are_folded_without_splitting_characters() -> None:
    line = "DESCRIPTION:" + "Ўзбекча изоҳ " * 20
    folded = fold(line)

    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == line
