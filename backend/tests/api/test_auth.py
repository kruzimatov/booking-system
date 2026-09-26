import uuid
from datetime import timedelta

import jwt
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from tests.support import DEFAULT_PASSWORD, FrozenClock, bearer_headers, make_user

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"


def register(client: TestClient, **overrides: object) -> Response:
    body = {"email": "ali@example.com", "password": DEFAULT_PASSWORD, "full_name": "Ali Valiyev"}
    return client.post(REGISTER_URL, json=body | overrides)


def login(
    client: TestClient, email: str = "client@example.com", password: str = DEFAULT_PASSWORD
) -> Response:
    return client.post(LOGIN_URL, json={"email": email, "password": password})


def error_code(response: Response) -> str:
    return str(response.json()["error"]["code"])


def test_register_creates_client_with_normalized_email(client: TestClient) -> None:
    response = register(client, email="Ali@Example.COM")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ali@example.com"
    assert body["role"] == "client"
    assert set(body) == {"id", "email", "full_name", "phone", "role"}


def test_register_rejects_duplicate_email_in_any_case(client: TestClient) -> None:
    register(client)
    response = register(client, email="ALI@example.com")

    assert response.status_code == 409
    assert error_code(response) == "EMAIL_TAKEN"


def test_register_rejects_role_field(client: TestClient) -> None:
    response = register(client, role="admin")

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
    assert "body.role" in response.json()["error"]["details"]["fields"]


def test_register_rejects_short_password(client: TestClient) -> None:
    response = register(client, password="short")

    assert response.status_code == 422
    assert "body.password" in response.json()["error"]["details"]["fields"]


def test_register_trims_name_but_keeps_password_spaces(client: TestClient) -> None:
    response = register(client, full_name="  Ali  ", password=" spaced password ")

    assert response.json()["full_name"] == "Ali"
    assert login(client, "ali@example.com", " spaced password ").status_code == 200
    assert login(client, "ali@example.com", "spaced password").status_code == 401


def test_login_returns_token_and_sets_http_only_cookie(client: TestClient, db: Session) -> None:
    make_user(db)
    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "client@example.com"
    cookie = response.headers["set-cookie"].lower()
    assert "access_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api" in cookie


def test_login_failure_does_not_reveal_whether_email_exists(
    client: TestClient, db: Session
) -> None:
    make_user(db)
    wrong_password = login(client, "client@example.com", "wrong-password")
    unknown_email = login(client, "nobody@example.com", "wrong-password")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_rejects_inactive_user(client: TestClient, db: Session) -> None:
    make_user(db, is_active=False)

    assert login(client).status_code == 401


def test_me_accepts_bearer_token(client: TestClient, db: Session, clock: FrozenClock) -> None:
    user = make_user(db)
    response = client.get(ME_URL, headers=bearer_headers(user, clock))

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


def test_me_accepts_cookie_from_login(client: TestClient, db: Session) -> None:
    make_user(db)
    login(client)

    assert client.get(ME_URL).status_code == 200


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get(ME_URL)

    assert response.status_code == 401
    assert error_code(response) == "UNAUTHENTICATED"


def test_me_rejects_expired_token(client: TestClient, db: Session, clock: FrozenClock) -> None:
    headers = bearer_headers(make_user(db), clock, ttl=timedelta(hours=1))
    clock.advance(timedelta(hours=1))

    assert client.get(ME_URL, headers=headers).status_code == 401


def test_me_rejects_user_deactivated_after_login(
    client: TestClient, db: Session, clock: FrozenClock
) -> None:
    user = make_user(db)
    headers = bearer_headers(user, clock)
    user.is_active = False
    db.commit()

    assert client.get(ME_URL, headers=headers).status_code == 401


def test_me_rejects_unsigned_token(client: TestClient, db: Session, clock: FrozenClock) -> None:
    user = make_user(db)
    payload = {"sub": str(user.id), "iat": clock.now(), "exp": clock.now() + timedelta(hours=1)}
    token = jwt.encode(payload, "", algorithm="none")

    assert client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_me_rejects_token_for_unknown_user(
    client: TestClient, db: Session, clock: FrozenClock
) -> None:
    ghost = make_user(db)
    headers = bearer_headers(ghost, clock)
    db.delete(ghost)
    db.commit()

    assert client.get(ME_URL, headers=headers).status_code == 401


def test_logout_clears_cookie(client: TestClient, db: Session) -> None:
    make_user(db)
    login(client)

    assert client.post(LOGOUT_URL).status_code == 204
    assert client.get(ME_URL).status_code == 401


def test_random_uuid_is_not_a_token(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {uuid.uuid4()}"}

    assert client.get(ME_URL, headers=headers).status_code == 401
