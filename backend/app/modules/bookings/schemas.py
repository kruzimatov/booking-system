import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, StringConstraints

from app.core.schemas import RequestSchema, ResponseSchema
from app.core.timezone import BusinessDateTime
from app.modules.bookings.models import BookingStatus

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class BookingCreate(RequestSchema):
    """ends_at, price and status are computed by the server; sending them is rejected."""

    provider_id: uuid.UUID
    service_id: uuid.UUID
    starts_at: AwareDatetime
    notes: Notes | None = None


class ServiceRef(ResponseSchema):
    id: uuid.UUID
    name: str
    duration_minutes: int


class ProviderRef(ResponseSchema):
    id: uuid.UUID
    full_name: str


class BookingOut(ResponseSchema):
    id: uuid.UUID
    status: BookingStatus
    starts_at: BusinessDateTime
    ends_at: BusinessDateTime
    price: Decimal
    notes: str | None
    service: ServiceRef
    provider: ProviderRef
    created_at: BusinessDateTime
