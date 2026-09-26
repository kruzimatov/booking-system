from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import UnauthenticatedError, translate_integrity_errors
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


class AuthService:
    def __init__(self, db: Session, clock: Clock, settings: Settings) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.clock = clock
        self.settings = settings

    def register(self, data: RegisterRequest) -> User:
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
            role=UserRole.CLIENT,
        )
        self.users.add(user)
        with translate_integrity_errors(self.db):
            self.db.commit()
        return user

    def login(self, data: LoginRequest) -> tuple[User, str]:
        user = self.users.get_by_email(data.email)
        password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        password_matches = verify_password(data.password, password_hash)
        if user is None or not password_matches or not user.is_active:
            raise UnauthenticatedError("Email or password is incorrect.")
        token = create_access_token(
            user.id,
            now=self.clock.now(),
            ttl=timedelta(minutes=self.settings.jwt_ttl_minutes),
            secret=self.settings.jwt_secret.get_secret_value(),
        )
        return user, token
