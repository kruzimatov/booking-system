from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import admin_router as catalog_admin_router
from app.modules.catalog.router import router as catalog_router
from app.modules.providers.router import admin_router as providers_admin_router
from app.modules.providers.router import router as providers_router
from app.modules.system.router import router as system_router

api_router = APIRouter(prefix="/api/v1")
for module_router in (
    auth_router,
    catalog_router,
    catalog_admin_router,
    providers_router,
    providers_admin_router,
    system_router,
):
    api_router.include_router(module_router)
