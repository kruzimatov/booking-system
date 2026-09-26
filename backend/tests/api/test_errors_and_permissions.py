from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import AdminUser
from app.modules.users.models import UserRole
from tests.support import FrozenClock, bearer_headers, make_user

ADMIN_PROBE_URL = "/api/v1/test/admin-probe"
CRASH_URL = "/api/v1/test/crash"


def add_test_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get(ADMIN_PROBE_URL)
    def admin_probe(user: AdminUser) -> dict[str, str]:
        return {"role": user.role}

    @router.get(CRASH_URL)
    def crash() -> None:
        raise RuntimeError("internal detail that must not leak")

    app.include_router(router)


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/auth/login")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_validation_error_lists_every_invalid_field(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={})

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert {"body.email", "body.password", "body.full_name"} <= set(fields)


def test_unexpected_error_hides_internal_details(api_app: FastAPI) -> None:
    add_test_routes(api_app)
    with TestClient(api_app, raise_server_exceptions=False) as client:
        response = client.get(CRASH_URL)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "internal detail" not in response.text


def test_admin_routes_reject_clients_and_allow_admins(
    api_app: FastAPI, db: Session, clock: FrozenClock
) -> None:
    add_test_routes(api_app)
    client_user = make_user(db, email="client@example.com")
    admin_user = make_user(db, email="admin@example.com", role=UserRole.ADMIN)

    with TestClient(api_app) as client:
        as_client = client.get(ADMIN_PROBE_URL, headers=bearer_headers(client_user, clock))
        as_admin = client.get(ADMIN_PROBE_URL, headers=bearer_headers(admin_user, clock))
        anonymous = client.get(ADMIN_PROBE_URL)

    assert as_client.status_code == 403
    assert as_client.json()["error"]["code"] == "FORBIDDEN"
    assert as_admin.status_code == 200
    assert anonymous.status_code == 401
