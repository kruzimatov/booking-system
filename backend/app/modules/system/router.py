from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import DbSession
from app.core.db import database_is_reachable
from app.core.errors import error_response

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check(db: DbSession) -> JSONResponse:
    if not database_is_reachable(db):
        return error_response(503, "DATABASE_UNAVAILABLE", "The database is not reachable.")
    return JSONResponse({"status": "ok"})
