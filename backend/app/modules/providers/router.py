import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, require_admin
from app.modules.providers.models import Provider
from app.modules.providers.schemas import (
    ProviderAdmin,
    ProviderCreate,
    ProviderPublic,
    ProviderServicesUpdate,
    ProviderUpdate,
)
from app.modules.providers.service import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])
admin_router = APIRouter(
    prefix="/admin/providers", tags=["admin: providers"], dependencies=[Depends(require_admin)]
)


def get_provider_service(db: DbSession) -> ProviderService:
    return ProviderService(db)


ProviderServiceDep = Annotated[ProviderService, Depends(get_provider_service)]


@router.get("", response_model=list[ProviderPublic])
def list_providers(
    providers: ProviderServiceDep, service_id: uuid.UUID | None = None
) -> list[Provider]:
    return providers.list_active(service_id)


@router.get("/{provider_id}", response_model=ProviderPublic)
def get_provider(provider_id: uuid.UUID, providers: ProviderServiceDep) -> Provider:
    return providers.get_active(provider_id)


@admin_router.get("", response_model=list[ProviderAdmin])
def admin_list_providers(providers: ProviderServiceDep) -> list[Provider]:
    return providers.list_all()


@admin_router.get("/{provider_id}", response_model=ProviderAdmin)
def admin_get_provider(provider_id: uuid.UUID, providers: ProviderServiceDep) -> Provider:
    return providers.get(provider_id)


@admin_router.post("", status_code=status.HTTP_201_CREATED, response_model=ProviderAdmin)
def create_provider(body: ProviderCreate, providers: ProviderServiceDep) -> Provider:
    return providers.create(body)


@admin_router.patch("/{provider_id}", response_model=ProviderAdmin)
def update_provider(
    provider_id: uuid.UUID, body: ProviderUpdate, providers: ProviderServiceDep
) -> Provider:
    return providers.update(provider_id, body)


@admin_router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_provider(provider_id: uuid.UUID, providers: ProviderServiceDep) -> None:
    providers.deactivate(provider_id)


@admin_router.put("/{provider_id}/services", response_model=ProviderAdmin)
def set_provider_services(
    provider_id: uuid.UUID, body: ProviderServicesUpdate, providers: ProviderServiceDep
) -> Provider:
    return providers.set_services(provider_id, body.service_ids)
