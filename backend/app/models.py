"""Every model imported in one place, so Alembic and relationship lookups see all tables."""

from app.core.base import Base
from app.modules.bookings.models import Booking, BookingEvent
from app.modules.catalog.models import Service
from app.modules.providers.models import Provider, provider_service_links
from app.modules.scheduling.models import AvailabilityWindow, TimeOff
from app.modules.users.models import User

__all__ = [
    "AvailabilityWindow",
    "Base",
    "Booking",
    "BookingEvent",
    "Provider",
    "Service",
    "TimeOff",
    "User",
    "provider_service_links",
]
