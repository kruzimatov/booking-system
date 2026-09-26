"""Test helpers: a controllable clock and small object factories."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.modules.users.models import User, UserRole

DEFAULT_PASSWORD = "correct-horse-battery"


class FrozenClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


def make_user(
    db: Session,
    *,
    email: str = "client@example.com",
    full_name: str = "Test Client",
    password: str = DEFAULT_PASSWORD,
    role: UserRole = UserRole.CLIENT,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    return user


def bearer_headers(
    user: User, clock: FrozenClock, ttl: timedelta = timedelta(hours=1)
) -> dict[str, str]:
    token = create_access_token(
        user.id, now=clock.now(), ttl=ttl, secret=get_settings().jwt_secret.get_secret_value()
    )
    return {"Authorization": f"Bearer {token}"}
