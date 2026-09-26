from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ClockDep, DbSession, SettingsDep, require_admin
from app.core.schemas import BoundedDate
from app.modules.admin.schemas import StatsOut
from app.modules.admin.service import StatsService

router = APIRouter(prefix="/admin", tags=["admin: stats"], dependencies=[Depends(require_admin)])


def get_stats_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> StatsService:
    return StatsService(db, clock, settings)


@router.get("/stats")
def get_stats(
    stats: Annotated[StatsService, Depends(get_stats_service)],
    date_from: BoundedDate | None = None,
    date_to: BoundedDate | None = None,
) -> StatsOut:
    """Business-local dates; defaults to the current month."""
    return stats.summary(date_from, date_to)
