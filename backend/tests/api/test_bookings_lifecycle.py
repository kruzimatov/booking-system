from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingStatus
from app.modules.catalog.models import Service
from app.modules.providers.models import Provider
from app.modules.users.models import User, UserRole
from tests.support import (
    FrozenClock,
    bearer_headers,
    make_booking,
    make_provider,
    make_service,
    make_user,
    make_week,
)

TEN_AM = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)  # Monday 10:00 Tashkent; clock is 08:00


@dataclass
class World:
    service: Service
    provider: Provider
    client: User
    client_headers: dict[str, str]
    admin_headers: dict[str, str]


@pytest.fixture
def world(db: Session, clock: FrozenClock) -> World:
    service = make_service(db, duration_minutes=60)
    provider = make_provider(db, services=[service])
    make_week(db, provider)
    client_user = make_user(db, email="client@example.com")
    admin = make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    return World(
        service,
        provider,
        client_user,
        # Long-lived tokens: these tests move the clock forward by hours.
        bearer_headers(client_user, clock, ttl=timedelta(hours=12)),
        bearer_headers(admin, clock, ttl=timedelta(hours=12)),
    )


def seed_booking(db: Session, world: World, starts_at: datetime = TEN_AM, **kwargs: Any) -> Booking:
    return make_booking(
        db,
        client=world.client,
        provider=world.provider,
        service=world.service,
        starts_at=starts_at,
        **kwargs,
    )


def client_cancel(client: TestClient, world: World, booking: Booking, **body: Any) -> Any:
    return client.post(
        f"/api/v1/bookings/{booking.id}/cancel", json=body or None, headers=world.client_headers
    )


def admin_action(client: TestClient, world: World, booking: Booking, action: str) -> Any:
    return client.post(f"/api/v1/admin/bookings/{booking.id}/{action}", headers=world.admin_headers)


def code(response: Any) -> str:
    return str(response.json()["error"]["code"])


def test_client_cancels_in_time_and_the_slot_is_free_again(
    client: TestClient, db: Session, world: World, clock: FrozenClock
) -> None:
    booking = seed_booking(db, world)
    response = client_cancel(client, world, booking, reason="Plans changed")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["allowed_actions"] == []

    other = bearer_headers(make_user(db, email="other@example.com"), clock)
    rebook = client.post(
        "/api/v1/bookings",
        json={
            "provider_id": str(world.provider.id),
            "service_id": str(world.service.id),
            "starts_at": "2030-01-07T10:00:00+05:00",
        },
        headers=other,
    )
    assert rebook.status_code == 201


def test_client_cannot_cancel_inside_the_cutoff(
    client: TestClient, db: Session, world: World, clock: FrozenClock
) -> None:
    booking = seed_booking(db, world)
    clock.advance(timedelta(hours=1, minutes=1))  # 09:01, less than 2h before 10:00

    response = client_cancel(client, world, booking)

    assert (response.status_code, code(response)) == (409, "CANCEL_TOO_LATE")
    assert (
        client.get(f"/api/v1/bookings/{booking.id}", headers=world.client_headers).json()[
            "allowed_actions"
        ]
        == []
    )


def test_admin_confirms_then_completes_after_the_end(
    client: TestClient, db: Session, world: World, clock: FrozenClock
) -> None:
    booking = seed_booking(db, world)

    confirmed = admin_action(client, world, booking, "confirm")
    assert confirmed.json()["status"] == "confirmed"
    early = admin_action(client, world, booking, "complete")
    assert (early.status_code, code(early)) == (409, "TOO_EARLY_TO_COMPLETE")

    clock.advance(timedelta(hours=3))  # 11:00, the booking ended at 11:00
    completed = admin_action(client, world, booking, "complete")

    assert completed.json()["status"] == "completed"
    history = [(event["from_status"], event["to_status"]) for event in completed.json()["events"]]
    # Seeded directly (no creation event); each status change is recorded in order.
    assert history == [("pending", "confirmed"), ("confirmed", "completed")]


def test_terminal_bookings_cannot_change(client: TestClient, db: Session, world: World) -> None:
    cancelled = seed_booking(db, world, status=BookingStatus.CANCELLED)

    for action in ("confirm", "cancel", "complete"):
        response = admin_action(client, world, cancelled, action)
        assert (response.status_code, code(response)) == (409, "INVALID_TRANSITION")


def test_clients_cannot_use_admin_actions_or_touch_other_bookings(
    client: TestClient, db: Session, world: World, clock: FrozenClock
) -> None:
    booking = seed_booking(db, world)
    stranger = bearer_headers(make_user(db, email="other@example.com"), clock)

    admin_endpoint = client.post(
        f"/api/v1/admin/bookings/{booking.id}/confirm", headers=world.client_headers
    )
    someone_else = client.post(f"/api/v1/bookings/{booking.id}/cancel", headers=stranger)

    assert admin_endpoint.status_code == 403
    assert someone_else.status_code == 404


def test_unknown_action_is_rejected(client: TestClient, db: Session, world: World) -> None:
    booking = seed_booking(db, world)

    assert admin_action(client, world, booking, "archive").status_code == 422


def test_admin_cancel_records_the_reason(client: TestClient, db: Session, world: World) -> None:
    booking = seed_booking(db, world)
    response = client.post(
        f"/api/v1/admin/bookings/{booking.id}/cancel",
        json={"reason": "Provider is ill"},
        headers=world.admin_headers,
    )

    body = response.json()
    assert body["cancel_reason"] == "Provider is ill"
    assert body["cancelled_at"] == "2030-01-07T08:00:00+05:00"
    assert body["events"][-1]["reason"] == "Provider is ill"


def test_client_downloads_a_calendar_file_for_own_booking_only(
    client: TestClient, db: Session, world: World, clock: FrozenClock
) -> None:
    booking = seed_booking(db, world)
    url = f"/api/v1/bookings/{booking.id}/calendar.ics"

    response = client.get(url, headers=world.client_headers)
    stranger = bearer_headers(make_user(db, email="other@example.com"), clock)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "attachment" in response.headers["content-disposition"]
    assert "DTSTART:20300107T050000Z" in response.text
    assert "SUMMARY:Haircut with Aziz Karimov" in response.text
    assert client.get(url, headers=stranger).status_code == 404
    assert client.get(url).status_code == 401
