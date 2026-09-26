"""Who may change a booking's status, and when. Pure: no database, no clock, no settings."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.bookings.models import BookingStatus


class Action(StrEnum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    COMPLETE = "complete"


# action -> (statuses it may start from, status it leads to). Cancelled and completed are final.
TRANSITIONS: dict[Action, tuple[frozenset[BookingStatus], BookingStatus]] = {
    Action.CONFIRM: (frozenset({BookingStatus.PENDING}), BookingStatus.CONFIRMED),
    Action.CANCEL: (
        frozenset({BookingStatus.PENDING, BookingStatus.CONFIRMED}),
        BookingStatus.CANCELLED,
    ),
    Action.COMPLETE: (frozenset({BookingStatus.CONFIRMED}), BookingStatus.COMPLETED),
}


class Refusal(StrEnum):
    FORBIDDEN = "FORBIDDEN"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    CANCEL_TOO_LATE = "CANCEL_TOO_LATE"
    TOO_EARLY_TO_COMPLETE = "TOO_EARLY_TO_COMPLETE"


@dataclass(frozen=True, slots=True)
class BookingFacts:
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class Viewer:
    is_admin: bool
    is_owner: bool


def refusal(
    action: Action,
    booking: BookingFacts,
    viewer: Viewer,
    *,
    now: datetime,
    cancel_cutoff: timedelta,
) -> Refusal | None:
    """Why the viewer may not perform the action now, or None if they may."""
    # Clients can only cancel their own bookings; confirming and completing is the business's job.
    if not viewer.is_admin and not (action is Action.CANCEL and viewer.is_owner):
        return Refusal.FORBIDDEN
    allowed_from, _ = TRANSITIONS[action]
    if booking.status not in allowed_from:
        return Refusal.INVALID_TRANSITION
    if action is Action.CANCEL and not viewer.is_admin and booking.starts_at - now < cancel_cutoff:
        return Refusal.CANCEL_TOO_LATE
    if action is Action.COMPLETE and booking.ends_at > now:
        return Refusal.TOO_EARLY_TO_COMPLETE
    return None


def allowed_actions(
    booking: BookingFacts, viewer: Viewer, *, now: datetime, cancel_cutoff: timedelta
) -> list[Action]:
    """Exposed in API responses, so the frontend never re-implements these rules."""
    return [
        action
        for action in Action
        if refusal(action, booking, viewer, now=now, cancel_cutoff=cancel_cutoff) is None
    ]
