import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.catalog.models import Service


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_services(self, *, active_only: bool) -> list[Service]:
        query = select(Service).order_by(Service.name, Service.id)
        if active_only:
            query = query.where(Service.is_active)
        return list(self.db.scalars(query))

    def get(self, service_id: uuid.UUID) -> Service | None:
        return self.db.get(Service, service_id)

    def get_many(self, service_ids: Collection[uuid.UUID]) -> list[Service]:
        if not service_ids:
            return []
        return list(self.db.scalars(select(Service).where(Service.id.in_(service_ids))))

    def add(self, service: Service) -> None:
        self.db.add(service)
