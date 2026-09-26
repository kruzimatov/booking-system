import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.modules.bookings.models import BookingStatus


class NamedCount(BaseModel):
    id: uuid.UUID
    name: str
    count: int


class StatsOut(BaseModel):
    date_from: date
    date_to: date
    counts_by_status: dict[BookingStatus, int]
    completed_revenue: Decimal
    currency: str
    bookings_per_provider: list[NamedCount]
    top_services: list[NamedCount]
