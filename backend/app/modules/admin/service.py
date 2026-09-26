from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import UnprocessableError
from app.core.timezone import local_day_bounds, local_today
from app.modules.admin.repository import StatsRepository
from app.modules.admin.schemas import NamedCount, StatsOut
from app.modules.bookings.models import BookingStatus

TOP_SERVICES = 5


def month_end(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


class StatsService:
    def __init__(self, db: Session, clock: Clock, settings: Settings) -> None:
        self.stats = StatsRepository(db)
        self.clock = clock
        self.settings = settings

    def summary(self, date_from: date | None, date_to: date | None) -> StatsOut:
        tz = self.settings.business_tz
        today = local_today(self.clock.now(), tz)
        # Missing ends default to the month of the given end, or to the current month.
        anchor = date_from or date_to or today
        first = date_from or anchor.replace(day=1)
        last = date_to or month_end(first)
        if first > last:
            raise UnprocessableError("date_from must not be after date_to.", code="INVALID_RANGE")
        start = local_day_bounds(first, tz)[0]
        end = local_day_bounds(last, tz)[1]
        counts = self.stats.counts_by_status(start, end)
        return StatsOut(
            date_from=first,
            date_to=last,
            counts_by_status={status: counts.get(status, 0) for status in BookingStatus},
            completed_revenue=self.stats.completed_revenue(start, end),
            currency=self.settings.currency,
            bookings_per_provider=[
                NamedCount(id=row[0], name=row[1], count=row[2])
                for row in self.stats.bookings_per_provider(start, end)
            ],
            top_services=[
                NamedCount(id=row[0], name=row[1], count=row[2])
                for row in self.stats.top_services(start, end, TOP_SERVICES)
            ],
        )
