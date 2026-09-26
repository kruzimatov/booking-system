from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingStatus
from tests.support import make_booking, make_provider, make_service, make_user

MONDAY_10 = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)


def test_stats_for_a_date_range(
    client: TestClient, db: Session, admin_headers: dict[str, str], client_headers: dict[str, str]
) -> None:
    haircut = make_service(db, name="Haircut", price="100000.00")
    shave = make_service(db, name="Shave", price="50000.00")
    aziz = make_provider(db, full_name="Aziz", services=[haircut, shave])
    customer = make_user(db, email="customer@example.com")
    for day, service, status in (
        (0, haircut, BookingStatus.COMPLETED),
        (1, haircut, BookingStatus.COMPLETED),
        (2, shave, BookingStatus.PENDING),
        (3, shave, BookingStatus.CANCELLED),
    ):
        make_booking(
            db,
            client=customer,
            provider=aziz,
            service=service,
            starts_at=MONDAY_10 + timedelta(days=day),
            status=status,
        )

    response = client.get(
        "/api/v1/admin/stats",
        params={"date_from": "2030-01-07", "date_to": "2030-01-10"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    stats = response.json()
    assert stats["counts_by_status"] == {
        "pending": 1,
        "confirmed": 0,
        "cancelled": 1,
        "completed": 2,
    }
    assert stats["completed_revenue"] == "200000.00"
    assert stats["bookings_per_provider"] == [{"id": str(aziz.id), "name": "Aziz", "count": 3}]
    assert [row["name"] for row in stats["top_services"]] == ["Haircut", "Shave"]
    assert client.get("/api/v1/admin/stats", headers=client_headers).status_code == 403


def test_stats_default_to_the_current_month(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    stats = client.get("/api/v1/admin/stats", headers=admin_headers).json()

    assert (stats["date_from"], stats["date_to"]) == ("2030-01-01", "2030-01-31")


def test_meta_exposes_the_booking_policy(client: TestClient) -> None:
    assert client.get("/api/v1/meta").json() == {
        "timezone": "Asia/Tashkent",
        "slot_step_minutes": 15,
        "min_notice_minutes": 60,
        "max_advance_days": 60,
        "cancel_cutoff_minutes": 120,
        "max_active_bookings_per_client": 5,
        "currency": "UZS",
    }


def test_stats_with_only_an_end_date_use_that_month(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    stats = client.get(
        "/api/v1/admin/stats", params={"date_to": "2029-11-20"}, headers=admin_headers
    ).json()

    assert (stats["date_from"], stats["date_to"]) == ("2029-11-01", "2029-11-20")


def test_date_filters_reject_absurd_years(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    for url, params in (
        ("/api/v1/admin/stats", {"date_from": "9999-12-31"}),
        ("/api/v1/admin/bookings", {"date_to": "9999-12-31"}),
    ):
        assert client.get(url, params=params, headers=admin_headers).status_code == 422
