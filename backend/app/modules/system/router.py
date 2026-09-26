from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import DbSession, SettingsDep
from app.core.db import database_is_reachable
from app.core.errors import error_response
from app.modules.catalog.models import DURATION_STEP_MINUTES

router = APIRouter(tags=["system"])


class MetaOut(BaseModel):
    """Booking policy for the frontend, so no rule is hard-coded twice."""

    timezone: str
    slot_step_minutes: int
    min_notice_minutes: int
    max_advance_days: int
    cancel_cutoff_minutes: int
    max_active_bookings_per_client: int
    currency: str


@router.get("/health")
def health_check(db: DbSession) -> JSONResponse:
    if not database_is_reachable(db):
        return error_response(503, "DATABASE_UNAVAILABLE", "The database is not reachable.")
    return JSONResponse({"status": "ok"})


@router.get("/meta")
def get_meta(settings: SettingsDep) -> MetaOut:
    return MetaOut(
        timezone=settings.business_timezone,
        slot_step_minutes=DURATION_STEP_MINUTES,
        min_notice_minutes=settings.min_notice_minutes,
        max_advance_days=settings.max_advance_days,
        cancel_cutoff_minutes=settings.cancel_cutoff_minutes,
        max_active_bookings_per_client=settings.max_active_bookings_per_client,
        currency=settings.currency,
    )
