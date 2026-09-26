import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.catalog.models import Service
from app.modules.providers.models import Provider, provider_service_links


class ProviderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_providers(
        self, *, active_only: bool, service_id: uuid.UUID | None = None
    ) -> list[Provider]:
        query = select(Provider).order_by(Provider.full_name, Provider.id)
        if active_only:
            query = query.where(Provider.is_active)
        if service_id is not None:
            query = (
                query.join(
                    provider_service_links, provider_service_links.c.provider_id == Provider.id
                )
                .join(Service, Service.id == provider_service_links.c.service_id)
                .where(Service.id == service_id)
            )
            if active_only:
                query = query.where(Service.is_active)
        return list(self.db.scalars(query))

    def get(self, provider_id: uuid.UUID) -> Provider | None:
        return self.db.get(Provider, provider_id)

    def lock(self, provider_id: uuid.UUID) -> Provider | None:
        # Row lock held until commit: serializes every change to one provider's schedule.
        query = select(Provider).where(Provider.id == provider_id).with_for_update()
        return self.db.scalar(query)

    def add(self, provider: Provider) -> None:
        self.db.add(provider)
