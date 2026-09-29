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


def _send(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        return
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.notification_from_email,
                "to": [to],
                "subject": subject,
                "text": body,
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send email to %s", to)


def send_booking_email(
    to_email: str,
    status: BookingStatus,
    client_name: str,
    service_name: str,
    provider_name: str,
    starts_at: datetime,
) -> None:
    settings = get_settings()
    subject = SUBJECT.get(status, "Booking update")
    body = _build_body(
        status,
        client_name,
        service_name,
        provider_name,
        starts_at,
        settings.business_tz,
    )
    _send(to_email, subject, body)


def notify_admin_new_booking(
    client_name: str,
    client_email: str,
    service_name: str,
    provider_name: str,
    starts_at: datetime,
) -> None:
    settings = get_settings()
    if not settings.notification_admin_email:
        return
    tz = settings.business_tz
    time_str = _format_time(starts_at, tz)
    _send(
        settings.notification_admin_email,
        f"New booking: {service_name} with {provider_name}",
        f"New booking from {client_name} ({client_email}).\n\n"
        f"Service: {service_name}\n"
        f"Specialist: {provider_name}\n"
        f"Time: {time_str}\n\n"
        "Log in to the admin panel to confirm or manage it.",
    )
