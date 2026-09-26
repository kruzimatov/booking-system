import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, UnprocessableError
from app.modules.catalog.repository import CatalogRepository
from app.modules.providers.models import Provider
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.schemas import ProviderCreate, ProviderUpdate


class ProviderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.providers = ProviderRepository(db)
        self.catalog = CatalogRepository(db)

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
        # Deactivation via PATCH and DELETE share one path; Phase 4 adds the future-bookings check.
        provider = self.get(provider_id)
        for field, value in data.changes().items():
            setattr(provider, field, value)
        self.db.commit()
        return provider

    def deactivate(self, provider_id: uuid.UUID) -> None:
        provider = self.get(provider_id)
        provider.is_active = False
        self.db.commit()

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
