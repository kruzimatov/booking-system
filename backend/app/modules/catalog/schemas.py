import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import AfterValidator, Field

from app.core.schemas import LongText, NameText, PatchSchema, RequestSchema, ResponseSchema
from app.modules.catalog.models import (
    BUFFER_STEP_MINUTES,
    DURATION_STEP_MINUTES,
    MAX_BUFFER_MINUTES,
    MAX_DURATION_MINUTES,
)

Duration = Annotated[
    int, Field(ge=DURATION_STEP_MINUTES, le=MAX_DURATION_MINUTES, multiple_of=DURATION_STEP_MINUTES)
]
Buffer = Annotated[int, Field(ge=0, le=MAX_BUFFER_MINUTES, multiple_of=BUFFER_STEP_MINUTES)]
CENT = Decimal("0.01")
# Always two decimals, so the API returns the same format before and after a database round trip.
Price = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
    AfterValidator(lambda value: value.quantize(CENT)),
]


class ServiceCreate(RequestSchema):
    name: NameText
    description: LongText | None = None
    duration_minutes: Duration
    buffer_minutes: Buffer = 0
    price: Price


class ServiceUpdate(PatchSchema):
    NOT_NULL: ClassVar[frozenset[str]] = frozenset(
        {"name", "duration_minutes", "buffer_minutes", "price", "is_active"}
    )

    name: NameText | None = None
    description: LongText | None = None
    duration_minutes: Duration | None = None
    buffer_minutes: Buffer | None = None
    price: Price | None = None
    is_active: bool | None = None


class ServicePublic(ResponseSchema):
    id: uuid.UUID
    name: str
    description: str | None
    duration_minutes: int
    price: Decimal


class ServiceAdmin(ServicePublic):
    buffer_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
