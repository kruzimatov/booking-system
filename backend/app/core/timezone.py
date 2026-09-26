from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import PlainSerializer

from app.core.config import get_settings


def to_business_tz(moment: datetime) -> datetime:
    return moment.astimezone(get_settings().business_tz)


def local_today(now: datetime, tz: ZoneInfo) -> date:
    # "Today" is the business's calendar day, not the server's (UTC) day.
    return now.astimezone(tz).date()


def local_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


# Stored and computed in UTC, returned to clients in business time with its offset (+05:00).
BusinessDateTime = Annotated[
    datetime, PlainSerializer(lambda moment: to_business_tz(moment).isoformat(), return_type=str)
]
