"""Demo data for reviewers: a small barbershop with three providers and a few bookings.

Usage (from backend/): uv run python -m scripts.seed --reset
Dates are relative to today, so the demo never goes stale.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import (
    AvailabilityWindow,
    Base,
    Booking,
    BookingEvent,
    Provider,
    Service,
    TimeOff,
    User,
)
from app.modules.bookings.models import BookingStatus
from app.modules.users.models import UserRole

ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
# Local defaults are published in the README; they are refused on an HTTPS deployment.
LOCAL_ADMIN_PASSWORD = "demo-admin-password"  # noqa: S105 (public local demo value)
LOCAL_CLIENT_PASSWORD = "demo-client-password"  # noqa: S105 (public local demo value)
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD") or LOCAL_ADMIN_PASSWORD
CLIENT_PASSWORD = os.environ.get("SEED_CLIENT_PASSWORD") or LOCAL_CLIENT_PASSWORD


@dataclass(frozen=True)
class Shift:
    weekdays: tuple[int, ...]
    windows: tuple[tuple[int, int], ...]


def reset(db: Session) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db.commit()


def next_workday(start: date, shift: Shift, step: int = 1) -> date:
    day = start
    while day.weekday() not in shift.weekdays:
        day += timedelta(days=step)
    return day


def at(day: date, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=tz).astimezone(UTC)


def seed(db: Session) -> None:
    tz = get_settings().business_tz
    today = SystemClock().now().astimezone(tz).date()

    admin = User(
        email=ADMIN_EMAIL,
        full_name="Shop Admin",
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
    )
    malika = User(
        email="client@example.com",
        full_name="Malika Tosheva",
        phone="+998901112233",
        password_hash=hash_password(CLIENT_PASSWORD),
    )
    jasur = User(
        email="jasur@example.com",
        full_name="Jasur Aliev",
        password_hash=hash_password(CLIENT_PASSWORD),
    )

    def service(name: str, minutes: int, buffer: int, price: str, about: str) -> Service:
        return Service(
            name=name,
            description=about,
            duration_minutes=minutes,
            buffer_minutes=buffer,
            price=Decimal(price),
        )

    haircut = service("Haircut", 45, 15, "120000", "Classic or modern cut, wash included.")
    beard = service("Beard trim", 30, 5, "60000", "Shape and trim with hot towel.")
    combo = service("Haircut and beard", 75, 15, "170000", "Both services in one visit.")
    kids = service("Kids haircut", 30, 5, "80000", "For children up to 12.")

    shifts = {
        "Aziz Karimov": Shift((0, 1, 2, 3, 4), ((9, 13), (14, 18))),
        "Bobur Rashidov": Shift((1, 2, 3, 4, 5), ((10, 19),)),
        "Dilnoza Yusupova": Shift((0, 2, 4), ((12, 20),)),
    }
    aziz = Provider(
        full_name="Aziz Karimov",
        bio="Senior barber, 8 years of experience.",
        services=[haircut, beard, combo],
    )
    bobur = Provider(
        full_name="Bobur Rashidov", bio="Beard specialist.", services=[haircut, beard, combo]
    )
    dilnoza = Provider(
        full_name="Dilnoza Yusupova", bio="Great with kids.", services=[haircut, kids]
    )
    db.add_all([admin, malika, jasur, aziz, bobur, dilnoza])
    db.flush()

    for provider in (aziz, bobur, dilnoza):
        shift = shifts[provider.full_name]
        db.add_all(
            AvailabilityWindow(
                provider_id=provider.id,
                weekday=weekday,
                start_time=time(start),
                end_time=time(end),
            )
            for weekday in shift.weekdays
            for start, end in shift.windows
        )

    bobur_off = next_workday(today + timedelta(days=7), shifts["Bobur Rashidov"])
    db.add(
        TimeOff(
            provider_id=bobur.id,
            starts_at=at(bobur_off, 14, 0, tz),
            ends_at=at(bobur_off, 19, 0, tz),
            reason="Training",
        )
    )

    def book(
        client: User,
        provider: Provider,
        service: Service,
        starts_at: datetime,
        history: tuple[BookingStatus, ...],
    ) -> None:
        ends_at = starts_at + timedelta(minutes=service.duration_minutes)
        booking = Booking(
            client_id=client.id,
            provider_id=provider.id,
            service_id=service.id,
            starts_at=starts_at,
            ends_at=ends_at,
            blocked_until=ends_at + timedelta(minutes=service.buffer_minutes),
            price=service.price,
            status=history[-1],
            cancelled_at=starts_at - timedelta(days=1)
            if history[-1] is BookingStatus.CANCELLED
            else None,
        )
        db.add(booking)
        db.flush()
        previous: BookingStatus | None = None
        for status in history:
            actor = client if status in (BookingStatus.PENDING, BookingStatus.CANCELLED) else admin
            db.add(
                BookingEvent(
                    booking_id=booking.id, actor_id=actor.id, from_status=previous, to_status=status
                )
            )
            previous = status

    pending, confirmed = BookingStatus.PENDING, BookingStatus.CONFIRMED
    completed, cancelled = BookingStatus.COMPLETED, BookingStatus.CANCELLED
    aziz_past = next_workday(today - timedelta(days=2), shifts["Aziz Karimov"], step=-1)
    aziz_next = next_workday(today + timedelta(days=1), shifts["Aziz Karimov"])
    bobur_next = next_workday(today + timedelta(days=1), shifts["Bobur Rashidov"])
    dilnoza_next = next_workday(today + timedelta(days=2), shifts["Dilnoza Yusupova"])

    book(malika, aziz, haircut, at(aziz_past, 10, 0, tz), (pending, confirmed, completed))
    book(jasur, aziz, combo, at(aziz_past, 14, 0, tz), (pending, cancelled))
    book(malika, aziz, beard, at(aziz_next, 11, 0, tz), (pending, confirmed))
    book(jasur, bobur, haircut, at(bobur_next, 12, 0, tz), (pending,))
    book(malika, dilnoza, kids, at(dilnoza_next, 15, 0, tz), (pending,))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    arguments = parser.parse_args()
    local_passwords = {LOCAL_ADMIN_PASSWORD, LOCAL_CLIENT_PASSWORD}
    if get_settings().cookie_secure and local_passwords & {ADMIN_PASSWORD, CLIENT_PASSWORD}:
        sys.exit(
            "Refusing to seed an HTTPS deployment with the public demo passwords. "
            "Set SEED_ADMIN_PASSWORD and SEED_CLIENT_PASSWORD in .env first."
        )
    with SessionLocal() as db:
        if arguments.reset:
            reset(db)
        seed(db)
    print("Demo data created.")
    print(f"  Admin:  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  Client: client@example.com / {CLIENT_PASSWORD}")
    print(f"  Client: jasur@example.com / {CLIENT_PASSWORD}")


if __name__ == "__main__":
    main()
