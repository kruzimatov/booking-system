import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import NameText, NormalizedEmail, PhoneText, RequestSchema, ResponseSchema
from app.modules.users.models import UserRole


class RegisterRequest(RequestSchema):
    email: NormalizedEmail
    # Passwords are never stripped: spaces are valid characters.
    password: str = Field(min_length=8, max_length=128)
    full_name: NameText
    phone: PhoneText | None = None


class LoginRequest(RequestSchema):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=128)


class UserOut(ResponseSchema):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (OAuth token type)
    user: UserOut
