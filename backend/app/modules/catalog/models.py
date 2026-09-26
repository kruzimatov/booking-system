from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKey

# Durations sit on the 15-minute slot grid, so every slot boundary lines up.
DURATION_STEP_MINUTES = 15
MAX_DURATION_MINUTES = 480
BUFFER_STEP_MINUTES = 5
MAX_BUFFER_MINUTES = 120


class Service(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            f"duration_minutes BETWEEN {DURATION_STEP_MINUTES} AND {MAX_DURATION_MINUTES} "
            f"AND mod(duration_minutes, {DURATION_STEP_MINUTES}) = 0",
            name="duration_valid",
        ),
        CheckConstraint(
            f"buffer_minutes BETWEEN 0 AND {MAX_BUFFER_MINUTES} "
            f"AND mod(buffer_minutes, {BUFFER_STEP_MINUTES}) = 0",
            name="buffer_valid",
        ),
        CheckConstraint("price >= 0", name="price_not_negative"),
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int]
    # Cleanup time after the appointment; blocks the provider but is not shown to clients.
    buffer_minutes: Mapped[int] = mapped_column(default=0, server_default="0")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
