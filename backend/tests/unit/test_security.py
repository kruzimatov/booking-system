import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-long-enough-0123456789"
NOW = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
TTL = timedelta(hours=1)


def test_password_hash_verifies_only_the_right_password() -> None:
    password_hash = hash_password("correct horse")
    assert password_hash != "correct horse"
    assert verify_password("correct horse", password_hash)
    assert not verify_password("wrong horse", password_hash)


def test_token_round_trip_returns_user_id() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, now=NOW, ttl=TTL, secret=SECRET)
    assert (
        decode_access_token(token, now=NOW + TTL - timedelta(seconds=1), secret=SECRET) == user_id
    )


def test_token_is_invalid_exactly_at_expiry() -> None:
    token = create_access_token(uuid.uuid4(), now=NOW, ttl=TTL, secret=SECRET)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=NOW + TTL, secret=SECRET)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = create_access_token(uuid.uuid4(), now=NOW, ttl=TTL, secret="another-secret-" + "x" * 30)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=NOW, secret=SECRET)


def test_unsigned_token_is_rejected() -> None:
    payload = {"sub": str(uuid.uuid4()), "iat": NOW, "exp": NOW + TTL}
    token = jwt.encode(payload, "", algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=NOW, secret=SECRET)


@pytest.mark.parametrize(
    "payload",
    [
        {"iat": NOW, "exp": NOW + TTL},
        {"sub": "not-a-uuid", "iat": NOW, "exp": NOW + TTL},
        {"sub": str(uuid.uuid4()), "iat": NOW},
    ],
    ids=["missing-subject", "subject-not-uuid", "missing-expiry"],
)
def test_malformed_token_is_rejected(payload: dict[str, object]) -> None:
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=NOW, secret=SECRET)


def test_settings_reject_short_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+psycopg://x/y", jwt_secret="short")  # type: ignore[call-arg, arg-type]
