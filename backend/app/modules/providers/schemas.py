import uuid
from datetime import datetime
from typing import ClassVar

from pydantic import Field, field_validator

from app.core.schemas import (
    LongText,
    NameText,
    NormalizedEmail,
    PatchSchema,
    PhoneText,
    RequestSchema,
    ResponseSchema,
)


class ProviderCreate(RequestSchema):
    full_name: NameText
    bio: LongText | None = None
    email: NormalizedEmail | None = None
    phone: PhoneText | None = None


class ProviderUpdate(PatchSchema):
    NOT_NULL: ClassVar[frozenset[str]] = frozenset({"full_name", "is_active"})

    full_name: NameText | None = None
    bio: LongText | None = None
    email: NormalizedEmail | None = None
    phone: PhoneText | None = None
    is_active: bool | None = None


class ProviderServicesUpdate(RequestSchema):
    service_ids: list[uuid.UUID] = Field(max_length=100)

    @field_validator("service_ids")
    @classmethod
    def ids_are_unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("service_ids must not contain duplicates")
        return value


class ProviderPublic(ResponseSchema):
    id: uuid.UUID
    full_name: str
    bio: str | None
    # Clients only see services they can actually book.
    service_ids: list[uuid.UUID] = Field(validation_alias="active_service_ids")


class ProviderAdmin(ResponseSchema):
    id: uuid.UUID
    full_name: str
    bio: str | None
    email: str | None
    phone: str | None
    is_active: bool
    service_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime
