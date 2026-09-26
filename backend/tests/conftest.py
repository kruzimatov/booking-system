import os

# Must run before the app is imported: the engine is created at import time.
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://booking:booking@localhost:5433/booking_test"
)
os.environ.setdefault("JWT_SECRET", "test-only-secret-that-is-at-least-32-characters")

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.db import SessionLocal, engine
from app.main import create_app
from app.models import Base
from app.modules.users.models import UserRole
from tests.support import FrozenClock, bearer_headers, make_user

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Monday 2030-01-07 08:00 in Tashkent (UTC+5): fixed, and far from real dates.
DEFAULT_NOW = datetime(2030, 1, 7, 3, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    # Real migrations, not create_all: raw-SQL constraints only exist in migrations.
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_tables(migrated_database: None) -> None:
    # TRUNCATE instead of rollback: concurrency tests commit from several connections.
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(DEFAULT_NOW)


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def api_app(clock: FrozenClock) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_clock] = lambda: clock
    return application


@pytest.fixture
def client(api_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(api_app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(db: Session, clock: FrozenClock) -> dict[str, str]:
    admin = make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    return bearer_headers(admin, clock)


@pytest.fixture
def client_headers(db: Session, clock: FrozenClock) -> dict[str, str]:
    return bearer_headers(make_user(db, email="client@example.com"), clock)
