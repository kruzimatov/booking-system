import uuid
from datetime import datetime, timedelta

import jwt
from pwdlib import PasswordHash

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_COOKIE = "access_token"  # noqa: S105 (cookie name, not a secret)

_password_hasher = PasswordHash.recommended()

# Checked when the email is unknown, so a failed login takes the same time either way.
DUMMY_PASSWORD_HASH = _password_hasher.hash("timing-equalizer")


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID, *, now: datetime, ttl: timedelta, secret: str) -> str:
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, now: datetime, secret: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            # Expiry is checked against the injected clock below, so tests can move time.
            options={"require": ["sub", "iat", "exp"], "verify_exp": False, "verify_iat": False},
        )
        expires_at = payload["exp"]
        subject = payload["sub"]
        if not isinstance(expires_at, int | float) or expires_at <= now.timestamp():
            raise InvalidTokenError("Token expired")
        return uuid.UUID(str(subject))
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError("Invalid token") from exc
