from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.router import api_router
from app.core.errors import register_error_handlers


def _operation_id(route: APIRoute) -> str:
    # Readable operation names in the generated frontend client (e.g. "login_user").
    return route.name


def create_app() -> FastAPI:
    # Docs live under /api because the frontend nginx only proxies /api to this service.
    app = FastAPI(
        title="Booking API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        generate_unique_id_function=_operation_id,
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
