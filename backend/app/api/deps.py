from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import ForbiddenError, UnauthenticatedError
from app.core.security import ACCESS_TOKEN_COOKIE, InvalidTokenError, decode_access_token
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_optional_user(
    request: Request,
    credentials: BearerCredentials,
    db: DbSession,
    clock: ClockDep,
    settings: SettingsDep,
) -> User | None:
    # Header first (Swagger, curl), then the httpOnly cookie set by the browser login.
    token = credentials.credentials if credentials else request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        return None
    try:
        user_id = decode_access_token(
            token, now=clock.now(), secret=settings.jwt_secret.get_secret_value()
        )
    except InvalidTokenError:
        return None
    # Loaded from the database on every request, so deactivation and role changes apply at once.
    user = UserRepository(db).get(user_id)
    return user if user is not None and user.is_active else None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(user: OptionalUser) -> User:
    if user is None:
        raise UnauthenticatedError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError()
    return user


AdminUser = Annotated[User, Depends(require_admin)]
