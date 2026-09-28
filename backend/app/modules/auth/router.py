from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep
from app.core.errors import UnprocessableError
from app.core.security import ACCESS_TOKEN_COOKIE, hash_password, verify_password
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# The cookie is only needed by API calls, so it is not sent with page and asset requests.
COOKIE_PATH = "/api"


def get_auth_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> AuthService:
    return AuthService(db, clock, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register_user(body: RegisterRequest, service: AuthServiceDep) -> User:
    return service.register(body)


@router.post("/login", response_model=TokenResponse)
def login_user(
    body: LoginRequest, response: Response, service: AuthServiceDep, settings: SettingsDep
) -> TokenResponse:
    user, token = service.login(body)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(response: Response, settings: SettingsDep) -> None:
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


@router.get("/me", response_model=UserOut)
def read_current_user(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(body: UpdateProfileRequest, user: CurrentUser, db: DbSession) -> User:
    for field, value in body.changes().items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordRequest, user: CurrentUser, db: DbSession) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise UnprocessableError("Current password is incorrect.", code="WRONG_PASSWORD")
    user.password_hash = hash_password(body.new_password)
    db.commit()
