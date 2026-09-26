import uuid
from collections import defaultdict
from datetime import time, timedelta
from itertools import pairwise
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.schemas import BoundedDatetime, RequestSchema, ResponseSchema
from app.core.timezone import BusinessDateTime
from app.modules.catalog.models import DURATION_STEP_MINUTES

MAX_WINDOWS_PER_DAY = 6
MAX_TIME_OFF = timedelta(days=365)


def _on_grid(value: time) -> bool:
    return (
        value.minute % DURATION_STEP_MINUTES == 0 and value.second == 0 and value.microsecond == 0
    )


class WindowIn(RequestSchema):
    weekday: int = Field(ge=0, le=6, description="0 = Monday, 6 = Sunday")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def valid_local_range(self) -> Self:
        if self.start_time.tzinfo is not None or self.end_time.tzinfo is not None:
            raise ValueError("Times are business-local wall-clock times without an offset")
        if not (_on_grid(self.start_time) and _on_grid(self.end_time)):
            raise ValueError(f"Times must be on the {DURATION_STEP_MINUTES}-minute grid")
        if self.end_time <= self.start_time:
            raise ValueError(
                "end_time must be after start_time (overnight shifts are not supported)"
            )
        return self


class AvailabilityReplace(RequestSchema):
    windows: list[WindowIn] = Field(max_length=7 * MAX_WINDOWS_PER_DAY)

    @model_validator(mode="after")
    def no_overlaps_per_weekday(self) -> Self:
        by_weekday: dict[int, list[WindowIn]] = defaultdict(list)
        for window in self.windows:
            by_weekday[window.weekday].append(window)
        for weekday, windows in by_weekday.items():
            if len(windows) > MAX_WINDOWS_PER_DAY:
                raise ValueError(f"At most {MAX_WINDOWS_PER_DAY} windows per weekday")
            ordered = sorted(windows, key=lambda window: window.start_time)
            for previous, current in pairwise(ordered):
                if current.start_time < previous.end_time:
                    raise ValueError(f"Windows overlap on weekday {weekday}")
        return self


class WindowOut(ResponseSchema):
    weekday: int
    start_time: time
    end_time: time


class TimeOffCreate(RequestSchema):
    starts_at: BoundedDatetime
    ends_at: BoundedDatetime
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.ends_at - self.starts_at > MAX_TIME_OFF:
            raise ValueError("Time off can be at most 365 days long")
        return self


class TimeOffOut(ResponseSchema):
    id: uuid.UUID
    starts_at: BusinessDateTime
    ends_at: BusinessDateTime
    reason: str | None


class SlotOut(BaseModel):
    starts_at: BusinessDateTime
    ends_at: BusinessDateTime
