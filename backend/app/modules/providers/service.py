import uuid

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.modules.bookings.repository import BookingRepository
from app.modules.catalog.repository import CatalogRepository
from app.modules.providers.models import Provider
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.schemas import ProviderCreate, ProviderUpdate


class ProviderService:
    def __init__(self, db: Session, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.providers = ProviderRepository(db)
        self.catalog = CatalogRepository(db)
        self.bookings = BookingRepository(db)

    def list_active(self, service_id: uuid.UUID | None = None) -> list[Provider]:
        return self.providers.list_providers(active_only=True, service_id=service_id)

    def list_all(self) -> list[Provider]:
        return self.providers.list_providers(active_only=False)

    def get_active(self, provider_id: uuid.UUID) -> Provider:
        provider = self.providers.get(provider_id)
        if provider is None or not provider.is_active:
            raise NotFoundError("Provider not found.")
        return provider

    def get(self, provider_id: uuid.UUID) -> Provider:
        provider = self.providers.get(provider_id)
        if provider is None:
            raise NotFoundError("Provider not found.")
        return provider

    def create(self, data: ProviderCreate) -> Provider:
        provider = Provider(**data.model_dump())
        self.providers.add(provider)
        self.db.commit()
        return provider

    def update(self, provider_id: uuid.UUID, data: ProviderUpdate) -> Provider:
        changes = data.changes()
        if changes.get("is_active") is False:
            self._ensure_can_deactivate(provider_id)
        provider = self.get(provider_id)
        for field, value in changes.items():
            setattr(provider, field, value)
        self.db.commit()
        return provider

    def deactivate(self, provider_id: uuid.UUID) -> None:
        self._ensure_can_deactivate(provider_id)
        provider = self.get(provider_id)
        provider.is_active = False
        self.db.commit()

    def _ensure_can_deactivate(self, provider_id: uuid.UUID) -> None:
        # PATCH is_active=false and DELETE both land here, under the provider lock.
        if self.providers.lock(provider_id) is None:
            raise NotFoundError("Provider not found.")
        upcoming = self.bookings.future_active_for_provider(provider_id, self.clock.now())
        if upcoming:
            raise ConflictError(
                f"The provider has {len(upcoming)} upcoming booking(s). Cancel them first.",
                code="PROVIDER_HAS_BOOKINGS",
                details={"booking_ids": [str(booking.id) for booking in upcoming]},
            )

    def set_services(self, provider_id: uuid.UUID, service_ids: list[uuid.UUID]) -> Provider:
        provider = self.get(provider_id)
        services = self.catalog.get_many(service_ids)
        missing = set(service_ids) - {service.id for service in services}
        if missing:
            raise UnprocessableError(
                "Some services do not exist.",
                code="UNKNOWN_SERVICES",
                details={"service_ids": sorted(str(service_id) for service_id in missing)},
            )
        # Removing a service here does not touch existing bookings; it only stops new ones.
        provider.services = services
        self.db.commit()
        self.db.refresh(provider)
        return provider
