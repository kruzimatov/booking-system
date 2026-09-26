import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ClockDep, DbSession, SettingsDep, require_admin
from app.core.schemas import BoundedDate
from app.modules.scheduling.models import AvailabilityWindow, TimeOff
from app.modules.scheduling.schemas import (
    AvailabilityReplace,
    SlotOut,
    TimeOffCreate,
    TimeOffOut,
    WindowOut,
)
from app.modules.scheduling.service import ScheduleService

router = APIRouter(prefix="/providers", tags=["scheduling"])
admin_router = APIRouter(
    prefix="/admin/providers", tags=["admin: scheduling"], dependencies=[Depends(require_admin)]
)


def get_schedule_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> ScheduleService:
    return ScheduleService(db, clock, settings)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]


@router.get("/{provider_id}/availability", response_model=list[WindowOut])
def get_availability(
    provider_id: uuid.UUID, schedule: ScheduleServiceDep
) -> list[AvailabilityWindow]:
    return schedule.get_availability(provider_id)


@router.get("/{provider_id}/slots", response_model=list[SlotOut])
def list_slots(
    provider_id: uuid.UUID,
    service_id: uuid.UUID,
    day: Annotated[BoundedDate, Query(alias="date", description="Business-local date, YYYY-MM-DD")],
    schedule: ScheduleServiceDep,
) -> list[SlotOut]:
    slots = schedule.get_slots(provider_id, service_id, day)
    return [SlotOut(starts_at=slot.start, ends_at=slot.end) for slot in slots]


@admin_router.put("/{provider_id}/availability", response_model=list[WindowOut])
def replace_availability(
    provider_id: uuid.UUID, body: AvailabilityReplace, schedule: ScheduleServiceDep
) -> list[AvailabilityWindow]:
    return schedule.replace_availability(provider_id, body.windows)


@admin_router.get("/{provider_id}/time-off", response_model=list[TimeOffOut])
def list_time_off(provider_id: uuid.UUID, schedule: ScheduleServiceDep) -> list[TimeOff]:
    return schedule.list_time_off(provider_id)


@admin_router.post(
    "/{provider_id}/time-off", status_code=status.HTTP_201_CREATED, response_model=TimeOffOut
)
def add_time_off(
    provider_id: uuid.UUID, body: TimeOffCreate, schedule: ScheduleServiceDep
) -> TimeOff:
    return schedule.add_time_off(provider_id, body)


@admin_router.delete(
    "/{provider_id}/time-off/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_time_off(
    provider_id: uuid.UUID, time_off_id: uuid.UUID, schedule: ScheduleServiceDep
) -> None:
    schedule.delete_time_off(provider_id, time_off_id)
