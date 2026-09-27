import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support import make_provider, make_service

PUBLIC_URL = "/api/v1/providers"
ADMIN_URL = "/api/v1/admin/providers"


def test_admin_creates_provider_and_public_view_hides_contacts(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    created = client.post(
        ADMIN_URL,
        json={
            "full_name": "Temurbek Xolmatov",
            "email": "Temurbek@Example.com",
            "phone": "+998901234567",
        },
        headers=admin_headers,
    )

    assert created.status_code == 201
    assert created.json()["email"] == "temurbek@example.com"

    public = client.get(f"{PUBLIC_URL}/{created.json()['id']}").json()
    assert set(public) == {"id", "full_name", "bio", "service_ids"}


def test_set_services_and_filter_public_list_by_service(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    haircut = make_service(db, name="Haircut")
    shave = make_service(db, name="Shave")
    temurbek = make_provider(db, full_name="Temurbek")
    make_provider(db, full_name="Farrux", services=[shave])

    response = client.put(
        f"{ADMIN_URL}/{temurbek.id}/services",
        json={"service_ids": [str(haircut.id)]},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["service_ids"] == [str(haircut.id)]
    offering_haircut = client.get(PUBLIC_URL, params={"service_id": str(haircut.id)}).json()
    assert [provider["full_name"] for provider in offering_haircut] == ["Temurbek"]


def test_inactive_service_is_not_offered_publicly(client: TestClient, db: Session) -> None:
    active = make_service(db, name="Active")
    retired = make_service(db, name="Retired", is_active=False)
    provider = make_provider(db, services=[active, retired])

    assert client.get(f"{PUBLIC_URL}/{provider.id}").json()["service_ids"] == [str(active.id)]
    assert client.get(PUBLIC_URL, params={"service_id": str(retired.id)}).json() == []


def test_set_services_rejects_unknown_and_duplicate_ids(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider = make_provider(db)
    service = make_service(db)
    unknown = uuid.uuid4()
    url = f"{ADMIN_URL}/{provider.id}/services"

    missing = client.put(
        url, json={"service_ids": [str(service.id), str(unknown)]}, headers=admin_headers
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "UNKNOWN_SERVICES"
    assert missing.json()["error"]["details"]["service_ids"] == [str(unknown)]

    duplicate = client.put(url, json={"service_ids": [str(service.id)] * 2}, headers=admin_headers)
    assert duplicate.status_code == 422


def test_set_services_with_empty_list_clears_them(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider = make_provider(db, services=[make_service(db)])
    response = client.put(
        f"{ADMIN_URL}/{provider.id}/services", json={"service_ids": []}, headers=admin_headers
    )

    assert response.json()["service_ids"] == []


def test_deactivated_provider_is_hidden_from_public(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    provider = make_provider(db)

    assert client.delete(f"{ADMIN_URL}/{provider.id}", headers=admin_headers).status_code == 204
    assert client.get(PUBLIC_URL).json() == []
    assert client.get(f"{PUBLIC_URL}/{provider.id}").status_code == 404
    assert client.get(ADMIN_URL, headers=admin_headers).json()[0]["is_active"] is False


def test_clients_cannot_manage_providers(
    client: TestClient, db: Session, client_headers: dict[str, str]
) -> None:
    provider = make_provider(db)

    assert (
        client.post(ADMIN_URL, json={"full_name": "X"}, headers=client_headers).status_code == 403
    )
    assert (
        client.put(
            f"{ADMIN_URL}/{provider.id}/services", json={"service_ids": []}, headers=client_headers
        ).status_code
        == 403
    )
