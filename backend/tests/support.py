"""Test helpers: a controllable clock and small object factories."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.modules.catalog.models import Service
from app.modules.providers.models import Provider
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


def make_service(
    db: Session,
    *,
    name: str = "Haircut",
    duration_minutes: int = 60,
    buffer_minutes: int = 0,
    price: str = "150000.00",
    is_active: bool = True,
) -> Service:
    service = Service(
        name=name,
        duration_minutes=duration_minutes,
        buffer_minutes=buffer_minutes,
        price=Decimal(price),
        is_active=is_active,
    )
    db.add(service)
    db.commit()
    return service


def make_provider(
    db: Session,
    *,
    full_name: str = "Aziz Karimov",
    services: Sequence[Service] = (),
    is_active: bool = True,
) -> Provider:
    provider = Provider(
        full_name=full_name,
        email="aziz@example.com",
        phone="+998901234567",
        is_active=is_active,
        services=list(services),
    )
    db.add(provider)
    db.commit()
    return provider
