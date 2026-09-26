import uuid
from datetime import datetime, time

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, UUIDPrimaryKey
from app.modules.catalog.models import DURATION_STEP_MINUTES

ON_GRID = (
    "mod(extract(minute from {column})::int, "
    + str(DURATION_STEP_MINUTES)
    + ") = 0 AND extract(second from {column}) = 0"
)


class AvailabilityWindow(UUIDPrimaryKey, Base):
    """Weekly recurring working hours in business-local wall-clock time."""

    __tablename__ = "availability_windows"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_valid"),
        CheckConstraint("end_time > start_time", name="time_order"),
        CheckConstraint(ON_GRID.format(column="start_time"), name="start_on_grid"),
        CheckConstraint(ON_GRID.format(column="end_time"), name="end_on_grid"),
        Index("ix_availability_windows_provider_weekday", "provider_id", "weekday"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = Monday
    start_time: Mapped[time]
    end_time: Mapped[time]


class TimeOff(UUIDPrimaryKey, Base):
    __tablename__ = "time_off"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="time_order"),
        Index("ix_time_off_provider_starts", "provider_id", "starts_at"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
