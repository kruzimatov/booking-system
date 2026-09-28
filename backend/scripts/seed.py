"""Demo data for reviewers: a grooming studio in Tashkent with five specialists.

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

ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@veraflow.uz")
# Local defaults are published in the README; they are refused on an HTTPS deployment.
LOCAL_ADMIN_PASSWORD = "demo-admin-password"  # noqa: S105 (public local demo value)
LOCAL_CLIENT_PASSWORD = "demo-client-password"  # noqa: S105 (public local demo value)
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD") or LOCAL_ADMIN_PASSWORD
CLIENT_PASSWORD = os.environ.get("SEED_CLIENT_PASSWORD") or LOCAL_CLIENT_PASSWORD

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    minutes: int
    buffer: int
    price: str
    description: str


@dataclass(frozen=True)
class SpecialistSpec:
    name: str
    bio: str
    services: tuple[str, ...]
    weekdays: tuple[int, ...]
    hours: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ClientSpec:
    email: str
    name: str
    phone: str | None


@dataclass(frozen=True)
class BookingSpec:
    days_from_today: int
    specialist: str
    service: str
    client: str
    start: time
    history: tuple[BookingStatus, ...]
    notes: str | None = None


SERVICES = (
    ServiceSpec("Classic haircut", 45, 15, "120000", "Scissor or clipper cut, wash and styling."),
    ServiceSpec("Skin fade", 60, 15, "150000", "Fade blended to the skin, razor line-up."),
    ServiceSpec("Beard shaping", 30, 5, "70000", "Trim and contour, finished with a hot towel."),
    ServiceSpec("Royal shave", 45, 10, "90000", "Straight-razor shave with hot towels and balm."),
    ServiceSpec(
        "Haircut and beard", 75, 15, "180000", "Classic haircut and beard shaping together."
    ),
    ServiceSpec("Kids haircut", 30, 5, "80000", "For children up to 12; cartoons included."),
    ServiceSpec("Hair colouring", 90, 15, "250000", "Single-tone colour or grey blending."),
    ServiceSpec("Scalp massage", 30, 5, "60000", "Relaxing head and scalp massage with warm oil."),
)

SPECIALISTS = (
    SpecialistSpec(
        "Temurbek Xolmatov",
        "Senior barber, nine years behind the chair. Classic cuts and clean fades.",
        ("Classic haircut", "Skin fade", "Beard shaping", "Haircut and beard"),
        (MON, TUE, WED, THU, FRI),
        ((10, 14), (15, 20)),
    ),
    SpecialistSpec(
        "Farrux Ergashev",
        "Fade specialist, trained in Istanbul. Books up fast on Saturdays.",
        ("Classic haircut", "Skin fade", "Beard shaping"),
        (TUE, WED, THU, FRI, SAT),
        ((11, 20),),
    ),
    SpecialistSpec(
        "Doniyor Qahhorov",
        "Master of the straight razor and the long, quiet shave.",
        ("Royal shave", "Beard shaping", "Haircut and beard"),
        (MON, WED, FRI, SAT),
        ((9, 13), (14, 18)),
    ),
    SpecialistSpec(
        "Sevara Mahmudova",
        "Children's favourite: calm hands, patience, and a lollipop at the end.",
        ("Kids haircut", "Classic haircut"),
        (MON, TUE, WED, THU),
        ((12, 19),),
    ),
    SpecialistSpec(
        "Nodira Ismoilova",
        "Colourist and scalp-care specialist.",
        ("Hair colouring", "Scalp massage"),
        (WED, THU, FRI, SAT, SUN),
        ((10, 17),),
    ),
)

CLIENTS = (
    ClientSpec("lazizbek1234@gmail.com", "Lazizbek Abdullayev", "+998 90 111 22 33"),
    ClientSpec("shahzod@example.com", "Shahzod Tursunov", "+998 93 245 67 18"),
    ClientSpec("kamola@example.com", "Kamola Saidova", None),
    ClientSpec("bekzod@example.com", "Bekzod Rahimov", "+998 97 700 12 40"),
    ClientSpec("ozoda@example.com", "Ozoda Nurmatova", None),
)

P, C, X, D = (
    BookingStatus.PENDING,
    BookingStatus.CONFIRMED,
    BookingStatus.CANCELLED,
    BookingStatus.COMPLETED,
)

# Past days move backwards and future days forwards to the specialist's nearest working day.
BOOKINGS = (
    BookingSpec(-3, "Temurbek Xolmatov", "Skin fade", "shahzod@example.com", time(10), (P, C, D)),
    BookingSpec(
        -3, "Nodira Ismoilova", "Hair colouring", "kamola@example.com", time(11), (P, C, D)
    ),
    BookingSpec(
        -2, "Doniyor Qahhorov", "Royal shave", "bekzod@example.com", time(9, 30), (P, C, D)
    ),
    BookingSpec(-2, "Farrux Ergashev", "Skin fade", "shahzod@example.com", time(12), (P, X)),
    BookingSpec(
        -1,
        "Sevara Mahmudova",
        "Kids haircut",
        "lazizbek1234@gmail.com",
        time(12, 30),
        (P, C, D),
        notes="For my son Amir, he is 6.",
    ),
    BookingSpec(1, "Temurbek Xolmatov", "Classic haircut", "shahzod@example.com", time(10), (P, C)),
    BookingSpec(1, "Temurbek Xolmatov", "Beard shaping", "bekzod@example.com", time(11), (P,)),
    BookingSpec(1, "Nodira Ismoilova", "Scalp massage", "lazizbek1234@gmail.com", time(14), (P,)),
    BookingSpec(2, "Farrux Ergashev", "Skin fade", "bekzod@example.com", time(17), (P, C)),
    BookingSpec(
        2,
        "Sevara Mahmudova",
        "Kids haircut",
        "ozoda@example.com",
        time(13),
        (P,),
        notes="Twins, please book the next slot for the second one too.",
    ),
    BookingSpec(3, "Doniyor Qahhorov", "Haircut and beard", "shahzod@example.com", time(14), (P,)),
    BookingSpec(4, "Nodira Ismoilova", "Hair colouring", "kamola@example.com", time(10), (P, C)),
)


def reset(db: Session) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db.commit()


def nearest_workday(start: date, weekdays: tuple[int, ...], step: int) -> date:
    day = start
    while day.weekday() not in weekdays:
        day += timedelta(days=step)
    return day


def at(day: date, moment: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, moment, tzinfo=tz).astimezone(UTC)


def seed(db: Session) -> None:
    tz = get_settings().business_tz
    today = SystemClock().now().astimezone(tz).date()

    admin = User(
        email=ADMIN_EMAIL,
        full_name="Studio Admin",
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
    )
    client_password = hash_password(CLIENT_PASSWORD)
    clients = {
        spec.email: User(
            email=spec.email, full_name=spec.name, phone=spec.phone, password_hash=client_password
        )
        for spec in CLIENTS
    }
    services = {
        spec.name: Service(
            name=spec.name,
            description=spec.description,
            duration_minutes=spec.minutes,
            buffer_minutes=spec.buffer,
            price=Decimal(spec.price),
        )
        for spec in SERVICES
    }
    shifts = {spec.name: spec for spec in SPECIALISTS}
    specialists = {
        spec.name: Provider(
            full_name=spec.name,
            bio=spec.bio,
            services=[services[name] for name in spec.services],
        )
        for spec in SPECIALISTS
    }
    db.add_all([admin, *clients.values(), *specialists.values()])
    db.flush()

    for spec in SPECIALISTS:
        db.add_all(
            AvailabilityWindow(
                provider_id=specialists[spec.name].id,
                weekday=weekday,
                start_time=time(start),
                end_time=time(end),
            )
            for weekday in spec.weekdays
            for start, end in spec.hours
        )

    last_booking_day: dict[str, date] = {}
    for booking in BOOKINGS:
        weekdays = shifts[booking.specialist].weekdays
        step = -1 if booking.days_from_today < 0 else 1
        day = nearest_workday(today + timedelta(days=booking.days_from_today), weekdays, step)
        last_booking_day[booking.specialist] = max(
            day, last_booking_day.get(booking.specialist, day)
        )
        add_booking(db, booking, day, tz, clients, specialists, services, admin)

    # Time off after each specialist's last demo booking, so no booking falls inside it.
    for name, reason, hours in (
        ("Farrux Ergashev", "Barber training", (time(14), time(20))),
        ("Nodira Ismoilova", "Day off", (time(10), time(17))),
    ):
        day = nearest_workday(last_booking_day[name] + timedelta(days=1), shifts[name].weekdays, 1)
        db.add(
            TimeOff(
                provider_id=specialists[name].id,
                starts_at=at(day, hours[0], tz),
                ends_at=at(day, hours[1], tz),
                reason=reason,
            )
        )
    db.commit()


def add_booking(
    db: Session,
    spec: BookingSpec,
    day: date,
    tz: ZoneInfo,
    clients: dict[str, User],
    specialists: dict[str, Provider],
    services: dict[str, Service],
    admin: User,
) -> None:
    client, service = clients[spec.client], services[spec.service]
    starts_at = at(day, spec.start, tz)
    ends_at = starts_at + timedelta(minutes=service.duration_minutes)
    final = spec.history[-1]
    booking = Booking(
        client_id=client.id,
        provider_id=specialists[spec.specialist].id,
        service_id=service.id,
        starts_at=starts_at,
        ends_at=ends_at,
        blocked_until=ends_at + timedelta(minutes=service.buffer_minutes),
        price=service.price,
        status=final,
        notes=spec.notes,
        cancelled_at=starts_at - timedelta(days=1) if final is BookingStatus.CANCELLED else None,
        cancel_reason="Plans changed" if final is BookingStatus.CANCELLED else None,
    )
    db.add(booking)
    db.flush()
    previous: BookingStatus | None = None
    for status in spec.history:
        actor = client if status in (BookingStatus.PENDING, BookingStatus.CANCELLED) else admin
        db.add(
            BookingEvent(
                booking_id=booking.id, actor_id=actor.id, from_status=previous, to_status=status
            )
        )
        previous = status


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
    print("Demo data created: a grooming studio with 5 specialists and 8 services.")
    print(f"  Admin:   {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    for spec in CLIENTS:
        print(f"  Client:  {spec.email} ({spec.name}) / {CLIENT_PASSWORD}")


if __name__ == "__main__":
    main()
