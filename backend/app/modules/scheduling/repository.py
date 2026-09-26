import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.scheduling.models import AvailabilityWindow, TimeOff


class ScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def windows(
        self, provider_id: uuid.UUID, weekday: int | None = None
    ) -> list[AvailabilityWindow]:
        query = (
            select(AvailabilityWindow)
            .where(AvailabilityWindow.provider_id == provider_id)
            .order_by(AvailabilityWindow.weekday, AvailabilityWindow.start_time)
        )
        if weekday is not None:
            query = query.where(AvailabilityWindow.weekday == weekday)
        return list(self.db.scalars(query))

    def replace_windows(
        self, provider_id: uuid.UUID, windows: Iterable[AvailabilityWindow]
    ) -> None:
        self.db.execute(
            delete(AvailabilityWindow).where(AvailabilityWindow.provider_id == provider_id)
        )
        self.db.add_all(windows)

    def time_off_between(
        self, provider_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[TimeOff]:
        query = (
            select(TimeOff)
            .where(TimeOff.provider_id == provider_id)
            .where(TimeOff.starts_at < end, TimeOff.ends_at > start)
            .order_by(TimeOff.starts_at)
        )
        return list(self.db.scalars(query))

    def upcoming_time_off(self, provider_id: uuid.UUID, now: datetime) -> list[TimeOff]:
        query = (
            select(TimeOff)
            .where(TimeOff.provider_id == provider_id, TimeOff.ends_at > now)
            .order_by(TimeOff.starts_at)
        )
        return list(self.db.scalars(query))

    def get_time_off(self, provider_id: uuid.UUID, time_off_id: uuid.UUID) -> TimeOff | None:
        query = select(TimeOff).where(TimeOff.id == time_off_id, TimeOff.provider_id == provider_id)
        return self.db.scalar(query)

    def add_time_off(self, time_off: TimeOff) -> None:
        self.db.add(time_off)

    def delete_time_off(self, time_off: TimeOff) -> None:
        self.db.delete(time_off)
