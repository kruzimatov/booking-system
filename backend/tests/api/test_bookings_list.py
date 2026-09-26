from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingStatus
from app.modules.users.models import UserRole
from tests.support import (
    FrozenClock,
    bearer_headers,
    make_booking,
    make_provider,
    make_service,
    make_user,
    make_week,
)

MONDAY_10 = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)  # clock is Monday 08:00 Tashkent


def test_client_sees_only_own_bookings_split_into_upcoming_and_history(
    client: TestClient, db: Session, clock: FrozenClock
) -> None:
    service = make_service(db)
    provider = make_provider(db, services=[service])
    make_week(db, provider)
    me = make_user(db, email="me@example.com")
    other = make_user(db, email="other@example.com")
    later = make_booking(
        db, client=me, provider=provider, service=service, starts_at=MONDAY_10 + timedelta(hours=4)
    )
    sooner = make_booking(db, client=me, provider=provider, service=service, starts_at=MONDAY_10)
    past = make_booking(
        db,
        client=me,
        provider=provider,
        service=service,
        starts_at=MONDAY_10 - timedelta(days=1),
        status=BookingStatus.COMPLETED,
    )
    cancelled = make_booking(
        db,
        client=me,
        provider=provider,
        service=service,
        starts_at=MONDAY_10 + timedelta(days=1),
        status=BookingStatus.CANCELLED,
    )
    make_booking(
        db,
        client=other,
        provider=provider,
        service=service,
        starts_at=MONDAY_10 + timedelta(hours=2),
    )
    headers = bearer_headers(me, clock)

    upcoming = client.get("/api/v1/bookings", headers=headers).json()
    history = client.get("/api/v1/bookings", params={"scope": "history"}, headers=headers).json()

    assert [item["id"] for item in upcoming["items"]] == [str(sooner.id), str(later.id)]
    assert upcoming["total"] == 2
    assert [item["id"] for item in history["items"]] == [str(cancelled.id), str(past.id)]


def test_pagination(client: TestClient, db: Session, clock: FrozenClock) -> None:
    service = make_service(db)
    provider = make_provider(db, services=[service])
    me = make_user(db, email="me@example.com")
    for day in range(5):
        make_booking(
            db,
            client=me,
            provider=provider,
            service=service,
            starts_at=MONDAY_10 + timedelta(days=day),
        )
    headers = bearer_headers(me, clock)

    second_page = client.get(
        "/api/v1/bookings", params={"page": 2, "size": 2}, headers=headers
    ).json()

    assert (second_page["total"], second_page["page"], second_page["size"]) == (5, 2, 2)
    assert len(second_page["items"]) == 2
    assert client.get("/api/v1/bookings", params={"size": 101}, headers=headers).status_code == 422


def test_admin_filters(client: TestClient, db: Session, clock: FrozenClock) -> None:
    service = make_service(db)
    aziz = make_provider(db, full_name="Aziz", services=[service])
    bobur = make_provider(db, full_name="Bobur", services=[service])
    me = make_user(db, email="me@example.com")
    admin = bearer_headers(make_user(db, email="admin@example.com", role=UserRole.ADMIN), clock)
    pending = make_booking(db, client=me, provider=aziz, service=service, starts_at=MONDAY_10)
    make_booking(
        db,
        client=me,
        provider=bobur,
        service=service,
        starts_at=MONDAY_10 + timedelta(days=1),
        status=BookingStatus.CONFIRMED,
    )

    def ids(**params: object) -> list[str]:
        page = client.get("/api/v1/admin/bookings", params=params, headers=admin).json()
        return [item["id"] for item in page["items"]]

    assert len(ids()) == 2
    assert ids(needs_action=True) == [str(pending.id)]
    assert ids(provider_id=str(aziz.id)) == [str(pending.id)]
    assert ids(date_from="2030-01-07", date_to="2030-01-07") == [str(pending.id)]
    assert len(ids(status=["pending", "confirmed"])) == 2
    reversed_range = client.get(
        "/api/v1/admin/bookings",
        params={"date_from": "2030-01-08", "date_to": "2030-01-07"},
        headers=admin,
    )
    assert reversed_range.status_code == 422
    first = client.get("/api/v1/admin/bookings", headers=admin).json()["items"][0]
    assert first["client"]["email"] == "me@example.com"
