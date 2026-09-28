import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.core.config import get_settings
from app.modules.bookings.models import BookingStatus

logger = logging.getLogger(__name__)

SUBJECT = {
    BookingStatus.PENDING: "Booking received",
    BookingStatus.CONFIRMED: "Booking confirmed",
    BookingStatus.CANCELLED: "Booking cancelled",
    BookingStatus.COMPLETED: "Thanks for visiting",
}


def _format_time(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%a %d %b, %H:%M")


def _build_body(
    status: BookingStatus,
    client_name: str,
    service_name: str,
    provider_name: str,
    starts_at: datetime,
    tz: ZoneInfo,
) -> str:
    time_str = _format_time(starts_at, tz)
    if status is BookingStatus.PENDING:
        return (
            f"Hi {client_name},\n\n"
            f"We received your booking for {service_name} with {provider_name} "
            f"on {time_str}.\n\n"
            "We will confirm it shortly."
        )
    if status is BookingStatus.CONFIRMED:
        return (
            f"Hi {client_name},\n\n"
            f"Your booking for {service_name} with {provider_name} "
            f"on {time_str} is confirmed.\n\n"
            "See you then!"
        )
    if status is BookingStatus.CANCELLED:
        return (
            f"Hi {client_name},\n\n"
            f"Your booking for {service_name} with {provider_name} "
            f"on {time_str} has been cancelled."
        )
    return (
        f"Hi {client_name},\n\n"
        f"Thanks for visiting! We hope you enjoyed your {service_name} "
        f"with {provider_name}."
    )


def send_booking_email(
    to_email: str,
    status: BookingStatus,
    client_name: str,
    service_name: str,
    provider_name: str,
    starts_at: datetime,
) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        return
    subject = SUBJECT.get(status, "Booking update")
    body = _build_body(
        status,
        client_name,
        service_name,
        provider_name,
        starts_at,
        settings.business_tz,
    )
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.notification_from_email,
                "to": [to_email],
                "subject": subject,
                "text": body,
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send email to %s", to_email)
