import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.catalog.models import Service
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import ServiceCreate, ServiceUpdate


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.services = CatalogRepository(db)

    def list_active(self) -> list[Service]:
        return self.services.list_services(active_only=True)

    def list_all(self) -> list[Service]:
        return self.services.list_services(active_only=False)

    def get_active(self, service_id: uuid.UUID) -> Service:
        # Inactive services are invisible to clients, so they get the same 404 as missing ones.
        service = self.services.get(service_id)
        if service is None or not service.is_active:
            raise NotFoundError("Service not found.")
        return service

    def get(self, service_id: uuid.UUID) -> Service:
        service = self.services.get(service_id)
        if service is None:
            raise NotFoundError("Service not found.")
        return service

    def create(self, data: ServiceCreate) -> Service:
        service = Service(**data.model_dump())
        self.services.add(service)
        self.db.commit()
        return service

    def update(self, service_id: uuid.UUID, data: ServiceUpdate) -> Service:
        # Existing bookings keep their own price and end time, so edits never rewrite history.
        service = self.get(service_id)
        for field, value in data.changes().items():
            setattr(service, field, value)
        self.db.commit()
        return service

    def deactivate(self, service_id: uuid.UUID) -> None:
        # Soft delete: bookings keep a valid reference and the service can be reactivated.
        service = self.get(service_id)
        service.is_active = False
        self.db.commit()
