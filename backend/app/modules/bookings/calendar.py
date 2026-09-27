"""iCalendar (RFC 5545) export of a booking. Pure: every value is passed in."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.bookings.models import BookingStatus

# Pending appointments are shown as tentative, so calendars can style them differently.
EVENT_STATUS = {
    BookingStatus.PENDING: "TENTATIVE",
    BookingStatus.CONFIRMED: "CONFIRMED",
    BookingStatus.COMPLETED: "CONFIRMED",
    BookingStatus.CANCELLED: "CANCELLED",
}
MAX_LINE_OCTETS = 75


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    booking_id: uuid.UUID
    service_name: str
    provider_name: str
    starts_at: datetime
    ends_at: datetime
    status: BookingStatus
    notes: str | None


def escape_text(value: str) -> str:
    """TEXT values escape backslash, semicolon, comma and newlines (RFC 5545 3.3.11)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a space (RFC 5545 3.1).

    Splits on character boundaries, so multi-byte UTF-8 characters are never cut.
    """
    parts: list[str] = []
    current, size = "", 0
    for character in line:
        width = len(character.encode())
        limit = MAX_LINE_OCTETS if not parts else MAX_LINE_OCTETS - 1  # continuation adds a space
        if size + width > limit:
            parts.append(current)
            current, size = "", 0
        current += character
        size += width
    parts.append(current)
    return "\r\n ".join(parts)


def utc_stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def to_ics(event: CalendarEvent, *, generated_at: datetime) -> str:
    description = f"Status: {event.status.value}"
    if event.notes:
        description += f"\nNotes: {event.notes}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Booking System//Appointments//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        # A stable UID lets calendars update the same event when it is downloaded again.
        f"UID:{event.booking_id}@booking-system",
        f"DTSTAMP:{utc_stamp(generated_at)}",
        f"DTSTART:{utc_stamp(event.starts_at)}",
        f"DTEND:{utc_stamp(event.ends_at)}",
        f"SUMMARY:{escape_text(f'{event.service_name} with {event.provider_name}')}",
        f"DESCRIPTION:{escape_text(description)}",
        f"STATUS:{EVENT_STATUS[event.status]}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "".join(fold(line) + "\r\n" for line in lines)
