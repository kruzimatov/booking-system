"""Real concurrent transactions against PostgreSQL.

Each worker gets its own session (its own connection) and waits on a barrier, so all
requests hit the database at the same moment. This proves the locks and the exclusion
constraints, not just the single-request logic.
"""

import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from psycopg.errors import ExclusionViolation
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.bookings.schemas import BookingCreate
from app.modules.bookings.service import BookingService
from app.modules.catalog.models import Service
from app.modules.providers.models import Provider
from app.modules.scheduling.schemas import TimeOffCreate
from app.modules.scheduling.service import ScheduleService
from tests.support import (
    FrozenClock,
    make_booking,
    make_provider,
    make_service,
    make_user,
    make_week,
)

TEN_AM = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)  # 10:00 in Tashkent, Monday


def run_concurrently(count: int, action: Callable[[Session, int], object]) -> Counter[str]:
    barrier = threading.Barrier(count)

    def worker(index: int) -> str:
        with SessionLocal() as session:
            barrier.wait()
            try:
                action(session, index)
            except AppError as error:
                return error.code
            return "ok"

    with ThreadPoolExecutor(count) as pool:
        return Counter(pool.map(worker, range(count)))


def active_bookings(db: Session) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(Booking).where(Booking.status == BookingStatus.PENDING)
        )
        or 0
    )


@pytest.fixture
def setup(db: Session) -> tuple[Service, Provider]:
    service = make_service(db, duration_minutes=60)
    provider = make_provider(db, services=[service])
    make_week(db, provider)
    return service, provider


def request(provider: Provider, service: Service, starts_at: datetime = TEN_AM) -> BookingCreate:
    return BookingCreate(provider_id=provider.id, service_id=service.id, starts_at=starts_at)


def test_ten_clients_racing_for_one_slot(
    db: Session, clock: FrozenClock, setup: tuple[Service, Provider]
) -> None:
    service, provider = setup
    clients = [make_user(db, email=f"client{i}@example.com") for i in range(10)]

    def book(session: Session, index: int) -> None:
        BookingService(session, clock, get_settings()).create(
            clients[index], request(provider, service)
        )

    results = run_concurrently(10, book)

    assert results == Counter({"ok": 1, "SLOT_TAKEN": 9})
    assert active_bookings(db) == 1


def test_partially_overlapping_requests_in_parallel(
    db: Session, clock: FrozenClock, setup: tuple[Service, Provider]
) -> None:
    service, provider = setup
    clients = [make_user(db, email=f"client{i}@example.com") for i in range(2)]
    starts = [TEN_AM, datetime(2030, 1, 7, 5, 30, tzinfo=UTC)]  # 10:00 and 10:30

    def book(session: Session, index: int) -> None:
        BookingService(session, clock, get_settings()).create(
            clients[index], request(provider, service, starts[index])
        )

    assert run_concurrently(2, book) == Counter({"ok": 1, "SLOT_TAKEN": 1})


def test_one_client_booking_two_providers_at_once(
    db: Session, clock: FrozenClock, setup: tuple[Service, Provider]
) -> None:
    service, first = setup
    second = make_provider(db, full_name="Bobur", services=[service])
    make_week(db, second)
    client = make_user(db)
    providers = [first, second]

    def book(session: Session, index: int) -> None:
        BookingService(session, clock, get_settings()).create(
            client, request(providers[index], service)
        )

    assert run_concurrently(2, book) == Counter({"ok": 1, "CLIENT_OVERLAP": 1})


def test_active_limit_holds_under_parallel_requests(
    db: Session, clock: FrozenClock, setup: tuple[Service, Provider]
) -> None:
    service, provider = setup
    client = make_user(db)
    settings = get_settings().model_copy(update={"max_active_bookings_per_client": 2})
    make_booking(db, client=client, provider=provider, service=service, starts_at=TEN_AM)
    starts = [datetime(2030, 1, 7, 7, 0, tzinfo=UTC), datetime(2030, 1, 7, 9, 0, tzinfo=UTC)]

    def book(session: Session, index: int) -> None:
        BookingService(session, clock, settings).create(
            client, request(provider, service, starts[index])
        )

    assert run_concurrently(2, book) == Counter({"ok": 1, "ACTIVE_LIMIT_REACHED": 1})


def test_booking_and_time_off_for_the_same_hour(
    db: Session, clock: FrozenClock, setup: tuple[Service, Provider]
) -> None:
    service, provider = setup
    client = make_user(db)
    time_off = TimeOffCreate(starts_at=TEN_AM, ends_at=datetime(2030, 1, 7, 6, 0, tzinfo=UTC))

    def act(session: Session, index: int) -> None:
        if index == 0:
            BookingService(session, clock, get_settings()).create(
                client, request(provider, service)
            )
        else:
            ScheduleService(session, clock, get_settings()).add_time_off(provider.id, time_off)

    results = run_concurrently(2, act)

    # Whichever commits first wins; the other sees it after the provider lock is released.
    assert results in (
        Counter({"ok": 1, "SCHEDULE_CONFLICT": 1}),
        Counter({"ok": 1, "PROVIDER_UNAVAILABLE": 1}),
    )


def test_database_rejects_overlap_even_without_the_application(
    db: Session, setup: tuple[Service, Provider]
) -> None:
    service, provider = setup
    first, second = make_user(db, email="a@example.com"), make_user(db, email="b@example.com")
    make_booking(db, client=first, provider=provider, service=service, starts_at=TEN_AM)

    with pytest.raises(IntegrityError) as raised:
        make_booking(
            db,
            client=second,
            provider=provider,
            service=service,
            starts_at=datetime(2030, 1, 7, 5, 30, tzinfo=UTC),
        )

    assert isinstance(raised.value.orig, ExclusionViolation)
    db.rollback()


def test_cancelled_bookings_do_not_block_the_database_constraint(
    db: Session, setup: tuple[Service, Provider]
) -> None:
    service, provider = setup
    first, second = make_user(db, email="a@example.com"), make_user(db, email="b@example.com")
    make_booking(
        db,
        client=first,
        provider=provider,
        service=service,
        starts_at=TEN_AM,
        status=BookingStatus.CANCELLED,
    )

    booking = make_booking(db, client=second, provider=provider, service=service, starts_at=TEN_AM)

    assert booking.id is not None
