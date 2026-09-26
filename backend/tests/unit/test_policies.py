from datetime import UTC, datetime, timedelta

import pytest

from app.modules.bookings.models import BookingStatus
from app.modules.bookings.policies import (
    Action,
    BookingFacts,
    Refusal,
    Viewer,
    allowed_actions,
    refusal,
)

NOW = datetime(2030, 1, 7, 3, 0, tzinfo=UTC)
CUTOFF = timedelta(hours=2)
ADMIN = Viewer(is_admin=True, is_owner=False)
OWNER = Viewer(is_admin=False, is_owner=True)
STRANGER = Viewer(is_admin=False, is_owner=False)


def booking(status: BookingStatus, starts_in: timedelta = timedelta(hours=5)) -> BookingFacts:
    starts_at = NOW + starts_in
    return BookingFacts(status=status, starts_at=starts_at, ends_at=starts_at + timedelta(hours=1))


def check(action: Action, facts: BookingFacts, viewer: Viewer) -> Refusal | None:
    return refusal(action, facts, viewer, now=NOW, cancel_cutoff=CUTOFF)


P, C, X, D = (
    BookingStatus.PENDING,
    BookingStatus.CONFIRMED,
    BookingStatus.CANCELLED,
    BookingStatus.COMPLETED,
)
PAST = timedelta(hours=-3)


@pytest.mark.parametrize(
    ("action", "status", "starts_in", "viewer", "expected"),
    [
        # Admin transitions
        (Action.CONFIRM, P, timedelta(hours=5), ADMIN, None),
        (Action.CONFIRM, P, PAST, ADMIN, None),  # late confirmation is allowed
        (Action.CONFIRM, C, timedelta(hours=5), ADMIN, Refusal.INVALID_TRANSITION),
        (Action.CANCEL, C, timedelta(minutes=10), ADMIN, None),  # admins ignore the cutoff
        (Action.COMPLETE, C, PAST, ADMIN, None),
        (Action.COMPLETE, C, timedelta(hours=5), ADMIN, Refusal.TOO_EARLY_TO_COMPLETE),
        (Action.COMPLETE, P, PAST, ADMIN, Refusal.INVALID_TRANSITION),
        # Terminal states
        (Action.CANCEL, X, timedelta(hours=5), ADMIN, Refusal.INVALID_TRANSITION),
        (Action.CONFIRM, D, PAST, ADMIN, Refusal.INVALID_TRANSITION),
        (Action.CANCEL, D, PAST, ADMIN, Refusal.INVALID_TRANSITION),
        # Client (owner)
        (Action.CANCEL, P, timedelta(hours=3), OWNER, None),
        (Action.CANCEL, C, timedelta(hours=2), OWNER, None),  # exactly at the cutoff
        (Action.CANCEL, C, timedelta(hours=1, minutes=59), OWNER, Refusal.CANCEL_TOO_LATE),
        (Action.CANCEL, X, timedelta(hours=5), OWNER, Refusal.INVALID_TRANSITION),
        (Action.CONFIRM, P, timedelta(hours=5), OWNER, Refusal.FORBIDDEN),
        (Action.COMPLETE, C, PAST, OWNER, Refusal.FORBIDDEN),
        # Another client
        (Action.CANCEL, P, timedelta(hours=5), STRANGER, Refusal.FORBIDDEN),
    ],
)
def test_transition_rules(
    action: Action,
    status: BookingStatus,
    starts_in: timedelta,
    viewer: Viewer,
    expected: Refusal | None,
) -> None:
    assert check(action, booking(status, starts_in), viewer) == expected


def test_allowed_actions_match_the_rules() -> None:
    upcoming_pending = booking(P)

    assert allowed_actions(upcoming_pending, ADMIN, now=NOW, cancel_cutoff=CUTOFF) == [
        Action.CONFIRM,
        Action.CANCEL,
    ]
    assert allowed_actions(upcoming_pending, OWNER, now=NOW, cancel_cutoff=CUTOFF) == [
        Action.CANCEL
    ]
    assert allowed_actions(booking(C, PAST), ADMIN, now=NOW, cancel_cutoff=CUTOFF) == [
        Action.CANCEL,
        Action.COMPLETE,
    ]
    assert allowed_actions(booking(X), OWNER, now=NOW, cancel_cutoff=CUTOFF) == []
