import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, require_admin
from app.modules.catalog.models import Service
from app.modules.catalog.schemas import ServiceAdmin, ServiceCreate, ServicePublic, ServiceUpdate
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/services", tags=["services"])
admin_router = APIRouter(
    prefix="/admin/services", tags=["admin: services"], dependencies=[Depends(require_admin)]
)


def get_catalog_service(db: DbSession) -> CatalogService:
    return CatalogService(db)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]


@router.get("", response_model=list[ServicePublic])
def list_services(catalog: CatalogServiceDep) -> list[Service]:
    return catalog.list_active()


@router.get("/{service_id}", response_model=ServicePublic)
def get_service(service_id: uuid.UUID, catalog: CatalogServiceDep) -> Service:
    return catalog.get_active(service_id)


@admin_router.get("", response_model=list[ServiceAdmin])
def admin_list_services(catalog: CatalogServiceDep) -> list[Service]:
    return catalog.list_all()


@admin_router.get("/{service_id}", response_model=ServiceAdmin)
def admin_get_service(service_id: uuid.UUID, catalog: CatalogServiceDep) -> Service:
    return catalog.get(service_id)


@admin_router.post("", status_code=status.HTTP_201_CREATED, response_model=ServiceAdmin)
def create_service(body: ServiceCreate, catalog: CatalogServiceDep) -> Service:
    return catalog.create(body)


@admin_router.patch("/{service_id}", response_model=ServiceAdmin)
def update_service(
    service_id: uuid.UUID, body: ServiceUpdate, catalog: CatalogServiceDep
) -> Service:
    return catalog.update(service_id, body)


@admin_router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_service(service_id: uuid.UUID, catalog: CatalogServiceDep) -> None:
    catalog.deactivate(service_id)
