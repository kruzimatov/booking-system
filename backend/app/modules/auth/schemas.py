import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, StringConstraints

from app.core.schemas import RequestSchema, ResponseSchema
from app.modules.users.models import UserRole

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=32)]


class RegisterRequest(RequestSchema):
    email: NormalizedEmail
    # Passwords are never stripped: spaces are valid characters.
    password: str = Field(min_length=8, max_length=128)
    full_name: FullName
    phone: Phone | None = None


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
