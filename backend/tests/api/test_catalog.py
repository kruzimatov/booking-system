import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.support import make_service

PUBLIC_URL = "/api/v1/services"
ADMIN_URL = "/api/v1/admin/services"
VALID_SERVICE = {"name": "Haircut", "duration_minutes": 60, "price": "150000"}


def test_admin_creates_service_and_public_sees_limited_fields(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    created = client.post(
        ADMIN_URL, json=VALID_SERVICE | {"buffer_minutes": 15}, headers=admin_headers
    )

    assert created.status_code == 201
    assert created.json()["buffer_minutes"] == 15
    assert created.json()["price"] == "150000.00"

    public = client.get(PUBLIC_URL).json()
    assert len(public) == 1
    assert set(public[0]) == {"id", "name", "description", "duration_minutes", "price"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duration_minutes", 20),
        ("duration_minutes", 0),
        ("duration_minutes", 495),
        ("buffer_minutes", 7),
        ("price", "-1"),
        ("price", "10.555"),
        ("name", "   "),
    ],
)
def test_create_rejects_invalid_values(
    client: TestClient, admin_headers: dict[str, str], field: str, value: object
) -> None:
    response = client.post(ADMIN_URL, json=VALID_SERVICE | {field: value}, headers=admin_headers)

    assert response.status_code == 422
    assert f"body.{field}" in response.json()["error"]["details"]["fields"]


def test_create_rejects_unknown_fields(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        ADMIN_URL, json=VALID_SERVICE | {"is_active": False}, headers=admin_headers
    )

    assert response.status_code == 422


def test_clients_and_anonymous_cannot_manage_services(
    client: TestClient, client_headers: dict[str, str]
) -> None:
    assert client.post(ADMIN_URL, json=VALID_SERVICE, headers=client_headers).status_code == 403
    assert client.post(ADMIN_URL, json=VALID_SERVICE).status_code == 401
    assert client.get(ADMIN_URL, headers=client_headers).status_code == 403


def test_patch_changes_only_sent_fields(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    service = make_service(db, name="Haircut")
    response = client.patch(
        f"{ADMIN_URL}/{service.id}",
        json={"price": "200000", "description": None},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["price"] == "200000.00"
    assert response.json()["name"] == "Haircut"


def test_patch_rejects_null_for_required_field(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    service = make_service(db)
    response = client.patch(f"{ADMIN_URL}/{service.id}", json={"name": None}, headers=admin_headers)

    assert response.status_code == 422


def test_deactivated_service_is_hidden_from_public_but_kept_for_admin(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    service = make_service(db)

    assert client.delete(f"{ADMIN_URL}/{service.id}", headers=admin_headers).status_code == 204
    assert client.get(PUBLIC_URL).json() == []
    assert client.get(f"{PUBLIC_URL}/{service.id}").status_code == 404
    assert (
        client.get(f"{ADMIN_URL}/{service.id}", headers=admin_headers).json()["is_active"] is False
    )

    reactivated = client.patch(
        f"{ADMIN_URL}/{service.id}", json={"is_active": True}, headers=admin_headers
    )
    assert reactivated.json()["is_active"] is True
    assert client.get(f"{PUBLIC_URL}/{service.id}").status_code == 200


def test_unknown_and_malformed_ids(client: TestClient) -> None:
    missing = client.get(f"{PUBLIC_URL}/{uuid.uuid4()}")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"{PUBLIC_URL}/not-a-uuid").status_code == 422


def test_database_rejects_duration_off_the_grid(db: Session) -> None:
    # The CHECK constraint guards the data even if a script bypasses the API validation.
    with pytest.raises(IntegrityError):
        make_service(db, duration_minutes=20)
