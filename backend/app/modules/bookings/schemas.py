import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from app.core.schemas import RequestSchema, ResponseSchema
from app.core.timezone import BusinessDateTime
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.policies import Action

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class BookingCreate(RequestSchema):
    """ends_at, price and status are computed by the server; sending them is rejected."""

    provider_id: uuid.UUID
    service_id: uuid.UUID
    starts_at: AwareDatetime
    notes: Notes | None = None


class CancelRequest(RequestSchema):
    reason: Reason | None = None


class ServiceRef(ResponseSchema):
    id: uuid.UUID
    name: str
    duration_minutes: int


class ProviderRef(ResponseSchema):
    id: uuid.UUID
    full_name: str


class ClientRef(ResponseSchema):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None


class BookingEventOut(ResponseSchema):
    from_status: BookingStatus | None
    to_status: BookingStatus
    actor_id: uuid.UUID
    reason: str | None
    created_at: BusinessDateTime


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
    # Computed per viewer on the server, so the frontend shows exactly the allowed buttons.
    allowed_actions: list[Action] = Field(default_factory=list)


class BookingAdminOut(BookingOut):
    client: ClientRef
    cancelled_at: BusinessDateTime | None
    cancel_reason: str | None
    events: list[BookingEventOut]
