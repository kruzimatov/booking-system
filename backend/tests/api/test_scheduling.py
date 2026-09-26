from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.catalog.models import Service
from app.modules.providers.models import Provider
from tests.support import make_provider, make_service

MONDAY = "2030-01-07"  # the frozen clock is Monday 08:00 in Tashkent
WORKING_WEEK = {
    "windows": [
        {"weekday": 0, "start_time": "09:00", "end_time": "13:00"},
        {"weekday": 0, "start_time": "14:00", "end_time": "18:00"},
    ]
}


def admin_url(provider: Provider, path: str) -> str:
    return f"/api/v1/admin/providers/{provider.id}/{path}"


def get_slots(client: TestClient, provider: Provider, service: Service, day: str = MONDAY) -> Any:
    return client.get(
        f"/api/v1/providers/{provider.id}/slots",
        params={"service_id": str(service.id), "date": day},
    )


def setup_provider(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> tuple[Provider, Service]:
    service = make_service(db, duration_minutes=60)
    provider = make_provider(db, services=[service])
    response = client.put(
        admin_url(provider, "availability"), json=WORKING_WEEK, headers=admin_headers
    )
    assert response.status_code == 200
    return provider, service


def test_slots_follow_working_hours_in_business_time(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider, service = setup_provider(client, db, admin_headers)
    starts = [slot["starts_at"] for slot in get_slots(client, provider, service).json()]

    assert starts[0] == "2030-01-07T09:00:00+05:00"
    assert starts[-1] == "2030-01-07T17:00:00+05:00"
    assert "2030-01-07T12:30:00+05:00" not in starts
    assert "2030-01-07T14:00:00+05:00" in starts


def test_day_off_returns_empty_list(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider, service = setup_provider(client, db, admin_headers)
    response = get_slots(client, provider, service, day="2030-01-13")

    assert response.status_code == 200
    assert response.json() == []


def test_dates_outside_the_booking_window_are_rejected(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider, service = setup_provider(client, db, admin_headers)

    for day in ("2030-01-06", "2030-03-09"):
        response = get_slots(client, provider, service, day=day)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DATE_OUT_OF_RANGE"
    assert get_slots(client, provider, service, day="2030-03-08").status_code == 200


def test_slots_require_an_active_provider_offering_the_service(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider, _ = setup_provider(client, db, admin_headers)
    other_service = make_service(db, name="Shave")
    inactive = make_provider(db, full_name="Gone", is_active=False, services=[other_service])

    not_offered = get_slots(client, provider, other_service)
    assert not_offered.status_code == 422
    assert not_offered.json()["error"]["code"] == "SERVICE_NOT_OFFERED"
    assert get_slots(client, inactive, other_service).status_code == 404


def test_time_off_removes_slots_and_deleting_it_restores_them(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider, service = setup_provider(client, db, admin_headers)
    created = client.post(
        admin_url(provider, "time-off"),
        json={
            "starts_at": "2030-01-07T12:00:00+05:00",
            "ends_at": "2030-01-07T15:00:00+05:00",
            "reason": "Doctor",
        },
        headers=admin_headers,
    )

    assert created.status_code == 201
    assert created.json()["starts_at"] == "2030-01-07T12:00:00+05:00"
    starts = [slot["starts_at"] for slot in get_slots(client, provider, service).json()]
    assert "2030-01-07T11:30:00+05:00" not in starts
    assert "2030-01-07T15:00:00+05:00" in starts

    deleted = client.delete(
        admin_url(provider, f"time-off/{created.json()['id']}"), headers=admin_headers
    )
    assert deleted.status_code == 204
    assert len(get_slots(client, provider, service).json()) == 26


def test_time_off_validation(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider = make_provider(db)
    url = admin_url(provider, "time-off")

    past = client.post(
        url,
        json={"starts_at": "2030-01-01T09:00:00+05:00", "ends_at": "2030-01-02T09:00:00+05:00"},
        headers=admin_headers,
    )
    naive = client.post(
        url,
        json={"starts_at": "2030-02-01T09:00", "ends_at": "2030-02-02T09:00"},
        headers=admin_headers,
    )
    reversed_range = client.post(
        url,
        json={"starts_at": "2030-02-02T09:00:00+05:00", "ends_at": "2030-02-01T09:00:00+05:00"},
        headers=admin_headers,
    )

    assert past.status_code == 422
    assert past.json()["error"]["code"] == "TIME_OFF_IN_PAST"
    assert naive.status_code == 422
    assert reversed_range.status_code == 422


def test_availability_validation(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider = make_provider(db)
    url = admin_url(provider, "availability")
    invalid = [
        [
            {"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
            {"weekday": 0, "start_time": "11:00", "end_time": "14:00"},
        ],
        [{"weekday": 0, "start_time": "09:10", "end_time": "12:00"}],
        [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}],
        [{"weekday": 7, "start_time": "09:00", "end_time": "12:00"}],
    ]

    for windows in invalid:
        assert client.put(url, json={"windows": windows}, headers=admin_headers).status_code == 422


def test_availability_replace_is_public_to_read_and_admin_only_to_write(
    client: TestClient, db: Session, admin_headers: dict[str, str], client_headers: dict[str, str]
) -> None:
    provider, _ = setup_provider(client, db, admin_headers)

    public = client.get(f"/api/v1/providers/{provider.id}/availability").json()
    assert public == [
        {"weekday": 0, "start_time": "09:00:00", "end_time": "13:00:00"},
        {"weekday": 0, "start_time": "14:00:00", "end_time": "18:00:00"},
    ]
    forbidden = client.put(
        admin_url(provider, "availability"), json=WORKING_WEEK, headers=client_headers
    )
    assert forbidden.status_code == 403
    cleared = client.put(
        admin_url(provider, "availability"), json={"windows": []}, headers=admin_headers
    )
    assert cleared.json() == []


def test_slots_reject_absurd_dates(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider, service = setup_provider(client, db, admin_headers)

    assert get_slots(client, provider, service, day="9999-12-31").status_code == 422
