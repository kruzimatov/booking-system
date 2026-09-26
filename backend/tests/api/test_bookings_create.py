from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingEvent, BookingStatus
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

BOOKINGS_URL = "/api/v1/bookings"
TEN_AM = "2030-01-07T10:00:00+05:00"  # Monday; the frozen clock is Monday 08:00 Tashkent


@dataclass
class Shop:
    service: Service
    provider: Provider
    client: User
    headers: dict[str, str]


@pytest.fixture
def shop(db: Session, clock: FrozenClock) -> Shop:
    service = make_service(db, duration_minutes=60, buffer_minutes=15)
    provider = make_provider(db, services=[service])
    make_week(db, provider)
    client = make_user(db, email="client@example.com")
    return Shop(service, provider, client, bearer_headers(client, clock))


def book(
    client: TestClient,
    shop: Shop,
    starts_at: str = TEN_AM,
    headers: dict[str, str] | None = None,
    **overrides: Any,
) -> Any:
    body = {
        "provider_id": str(shop.provider.id),
        "service_id": str(shop.service.id),
        "starts_at": starts_at,
    } | overrides
    return client.post(BOOKINGS_URL, json=body, headers=headers or shop.headers)


def error_code(response: Any) -> str:
    return str(response.json()["error"]["code"])


def test_booking_is_created_pending_with_server_computed_fields(
    client: TestClient, db: Session, shop: Shop
) -> None:
    response = book(client, shop, notes="First visit")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["starts_at"] == TEN_AM
    assert body["ends_at"] == "2030-01-07T11:00:00+05:00"
    assert body["price"] == "150000.00"
    assert body["service"]["name"] == "Haircut"
    assert body["provider"]["full_name"] == "Aziz Karimov"
    events = db.scalars(select(BookingEvent)).all()
    assert [(event.from_status, event.to_status) for event in events] == [
        (None, BookingStatus.PENDING)
    ]


def test_client_cannot_send_server_owned_fields(client: TestClient, shop: Shop) -> None:
    for field, value in (("ends_at", TEN_AM), ("price", "1"), ("status", "confirmed")):
        assert book(client, shop, **{field: value}).status_code == 422


def test_naive_start_time_is_rejected(client: TestClient, shop: Shop) -> None:
    assert book(client, shop, starts_at="2030-01-07T10:00:00").status_code == 422


@pytest.mark.parametrize(
    ("starts_at", "status", "code"),
    [
        ("2030-01-07T10:10:00+05:00", 422, "SLOT_OFF_GRID"),
        ("2030-01-07T08:45:00+05:00", 422, "SLOT_TOO_SOON"),
        ("2030-03-09T10:00:00+05:00", 422, "SLOT_TOO_FAR"),
        ("2030-01-07T12:30:00+05:00", 422, "OUTSIDE_WORKING_HOURS"),
        ("2030-01-07T17:15:00+05:00", 422, "OUTSIDE_WORKING_HOURS"),
    ],
)
def test_start_time_rules(
    client: TestClient, shop: Shop, starts_at: str, status: int, code: str
) -> None:
    response = book(client, shop, starts_at=starts_at)

    assert response.status_code == status
    assert error_code(response) == code


def test_same_instant_in_another_offset_is_the_same_slot(
    client: TestClient, db: Session, shop: Shop, clock: FrozenClock
) -> None:
    assert book(client, shop, starts_at="2030-01-07T05:00:00Z").status_code == 201
    other = make_user(db, email="other@example.com")
    response = book(client, shop, headers=bearer_headers(other, clock))

    assert response.status_code == 409
    assert error_code(response) == "SLOT_TAKEN"


def test_taken_slot_and_buffer_are_blocked_for_others(
    client: TestClient, db: Session, shop: Shop, clock: FrozenClock
) -> None:
    assert book(client, shop).status_code == 201
    other = bearer_headers(make_user(db, email="other@example.com"), clock)

    partial = book(client, shop, starts_at="2030-01-07T10:30:00+05:00", headers=other)
    in_buffer = book(client, shop, starts_at="2030-01-07T11:00:00+05:00", headers=other)
    after_buffer = book(client, shop, starts_at="2030-01-07T11:15:00+05:00", headers=other)

    assert (partial.status_code, error_code(partial)) == (409, "SLOT_TAKEN")
    assert (in_buffer.status_code, error_code(in_buffer)) == (409, "SLOT_TAKEN")
    assert after_buffer.status_code == 201


def test_slots_endpoint_hides_booked_time(client: TestClient, shop: Shop) -> None:
    book(client, shop)
    slots = client.get(
        f"/api/v1/providers/{shop.provider.id}/slots",
        params={"service_id": str(shop.service.id), "date": "2030-01-07"},
    ).json()
    starts = {slot["starts_at"] for slot in slots}

    assert TEN_AM not in starts
    # 09:00 ends at 10:00, but its 15-minute buffer would run into the 10:00 booking.
    assert "2030-01-07T09:00:00+05:00" not in starts
    assert "2030-01-07T08:45:00+05:00" not in starts  # before opening time
    assert "2030-01-07T11:00:00+05:00" not in starts  # inside the 15-minute buffer
    assert "2030-01-07T11:15:00+05:00" in starts


def test_client_cannot_be_in_two_places_at_once(
    client: TestClient, db: Session, shop: Shop
) -> None:
    second_provider = make_provider(db, full_name="Bobur", services=[shop.service])
    make_week(db, second_provider)
    assert book(client, shop).status_code == 201

    response = book(client, shop, provider_id=str(second_provider.id))

    assert (response.status_code, error_code(response)) == (409, "CLIENT_OVERLAP")


def test_active_booking_limit(client: TestClient, shop: Shop) -> None:
    # 60-minute service + 15-minute buffer: five non-overlapping Monday bookings.
    for start in ("09:00", "10:30", "12:00", "14:00", "15:30"):
        assert book(client, shop, starts_at=f"2030-01-07T{start}:00+05:00").status_code == 201

    response = book(client, shop, starts_at="2030-01-07T17:00:00+05:00")

    assert (response.status_code, error_code(response)) == (409, "ACTIVE_LIMIT_REACHED")


def test_unknown_inactive_or_unoffered_resources(
    client: TestClient, db: Session, shop: Shop
) -> None:
    inactive = make_provider(db, full_name="Gone", services=[shop.service], is_active=False)
    unoffered = make_service(db, name="Shave")

    assert book(client, shop, provider_id=str(inactive.id)).status_code == 404
    offered = book(client, shop, service_id=str(unoffered.id))
    assert (offered.status_code, error_code(offered)) == (422, "SERVICE_NOT_OFFERED")


def test_admins_cannot_book(
    client: TestClient, db: Session, shop: Shop, clock: FrozenClock
) -> None:
    admin = make_user(db, email="admin@example.com", role=UserRole.ADMIN)

    assert book(client, shop, headers=bearer_headers(admin, clock)).status_code == 403


def test_booking_visibility(
    client: TestClient, db: Session, shop: Shop, clock: FrozenClock
) -> None:
    booking_id = book(client, shop).json()["id"]
    stranger = bearer_headers(make_user(db, email="other@example.com"), clock)
    admin = bearer_headers(make_user(db, email="admin@example.com", role=UserRole.ADMIN), clock)
    url = f"{BOOKINGS_URL}/{booking_id}"

    assert client.get(url, headers=shop.headers).status_code == 200
    assert client.get(url, headers=stranger).status_code == 404
    assert client.get(f"/api/v1/admin/bookings/{booking_id}", headers=admin).status_code == 200
    assert client.get(f"/api/v1/admin/bookings/{booking_id}", headers=stranger).status_code == 403


def test_price_is_a_snapshot(
    client: TestClient, db: Session, shop: Shop, admin_headers: dict[str, str]
) -> None:
    booking_id = book(client, shop).json()["id"]
    client.patch(
        f"/api/v1/admin/services/{shop.service.id}", json={"price": "999000"}, headers=admin_headers
    )

    assert client.get(f"{BOOKINGS_URL}/{booking_id}", headers=shop.headers).json()["price"] == (
        "150000.00"
    )


def test_schedule_changes_cannot_orphan_bookings(
    client: TestClient, db: Session, shop: Shop, admin_headers: dict[str, str]
) -> None:
    booking_id = book(client, shop).json()["id"]
    base = f"/api/v1/admin/providers/{shop.provider.id}"

    afternoon_only = client.put(
        f"{base}/availability",
        json={"windows": [{"weekday": 0, "start_time": "14:00", "end_time": "18:00"}]},
        headers=admin_headers,
    )
    time_off = client.post(
        f"{base}/time-off",
        json={"starts_at": "2030-01-07T10:30:00+05:00", "ends_at": "2030-01-07T12:00:00+05:00"},
        headers=admin_headers,
    )
    deactivate = client.delete(base, headers=admin_headers)
    patch_inactive = client.patch(base, json={"is_active": False}, headers=admin_headers)

    for response, code in (
        (afternoon_only, "SCHEDULE_CONFLICT"),
        (time_off, "SCHEDULE_CONFLICT"),
        (deactivate, "PROVIDER_HAS_BOOKINGS"),
        (patch_inactive, "PROVIDER_HAS_BOOKINGS"),
    ):
        assert (response.status_code, error_code(response)) == (409, code)
        assert response.json()["error"]["details"]["booking_ids"] == [booking_id]


def test_past_bookings_do_not_block_schedule_changes(
    client: TestClient, db: Session, shop: Shop, admin_headers: dict[str, str]
) -> None:
    make_booking(
        db,
        client=shop.client,
        provider=shop.provider,
        service=shop.service,
        starts_at=datetime(2030, 1, 6, 5, 0, tzinfo=UTC),
    )

    response = client.delete(f"/api/v1/admin/providers/{shop.provider.id}", headers=admin_headers)

    assert response.status_code == 204
