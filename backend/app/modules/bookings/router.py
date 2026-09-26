import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AdminUser, ClientUser, ClockDep, DbSession, SettingsDep, require_admin
from app.core.schemas import Page
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.bookings.policies import Action
from app.modules.bookings.schemas import BookingAdminOut, BookingCreate, BookingOut, CancelRequest
from app.modules.bookings.service import BookingService
from app.modules.users.models import User

router = APIRouter(prefix="/bookings", tags=["bookings"])
admin_router = APIRouter(
    prefix="/admin/bookings", tags=["admin: bookings"], dependencies=[Depends(require_admin)]
)

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def get_booking_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> BookingService:
    return BookingService(db, clock, settings)


BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]


def to_client_view(bookings: BookingService, viewer: User, booking: Booking) -> BookingOut:
    view = BookingOut.model_validate(booking)
    view.allowed_actions = bookings.actions_for(viewer, booking)
    return view


def to_admin_view(bookings: BookingService, viewer: User, booking: Booking) -> BookingAdminOut:
    view = BookingAdminOut.model_validate(booking)
    view.allowed_actions = bookings.actions_for(viewer, booking)
    return view


@router.post("", status_code=status.HTTP_201_CREATED)
def create_booking(
    body: BookingCreate, client: ClientUser, bookings: BookingServiceDep
) -> BookingOut:
    return to_client_view(bookings, client, bookings.create(client, body))


@router.get("")
def list_my_bookings(
    client: ClientUser,
    bookings: BookingServiceDep,
    scope: Literal["upcoming", "history"] = "upcoming",
    page: PageNumber = 1,
    size: PageSize = 20,
) -> Page[BookingOut]:
    items, total = bookings.list_own(client, scope=scope, page=page, size=size)
    views = [to_client_view(bookings, client, booking) for booking in items]
    return Page(items=views, total=total, page=page, size=size)


@router.get("/{booking_id}")
def get_my_booking(
    booking_id: uuid.UUID, client: ClientUser, bookings: BookingServiceDep
) -> BookingOut:
    return to_client_view(bookings, client, bookings.get_own(client, booking_id))


@router.post("/{booking_id}/cancel")
def cancel_my_booking(
    booking_id: uuid.UUID,
    client: ClientUser,
    bookings: BookingServiceDep,
    body: CancelRequest | None = None,
) -> BookingOut:
    reason = body.reason if body else None
    booking = bookings.apply(client, booking_id, Action.CANCEL, reason)
    return to_client_view(bookings, client, booking)


@admin_router.get("")
def admin_list_bookings(
    admin: AdminUser,
    bookings: BookingServiceDep,
    status_in: Annotated[list[BookingStatus] | None, Query(alias="status")] = None,
    provider_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    needs_action: bool = False,
    page: PageNumber = 1,
    size: PageSize = 20,
) -> Page[BookingAdminOut]:
    # "Needs action" = still pending: the business has not confirmed it yet.
    statuses = [BookingStatus.PENDING] if needs_action else (status_in or [])
    items, total = bookings.list_all(
        statuses=statuses,
        provider_id=provider_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    views = [to_admin_view(bookings, admin, booking) for booking in items]
    return Page(items=views, total=total, page=page, size=size)


@admin_router.get("/{booking_id}")
def admin_get_booking(
    booking_id: uuid.UUID, admin: AdminUser, bookings: BookingServiceDep
) -> BookingAdminOut:
    return to_admin_view(bookings, admin, bookings.get_any(booking_id))


@admin_router.post("/{booking_id}/{action}")
def admin_change_booking_status(
    booking_id: uuid.UUID,
    action: Action,
    admin: AdminUser,
    bookings: BookingServiceDep,
    body: CancelRequest | None = None,
) -> BookingAdminOut:
    reason = body.reason if body else None
    return to_admin_view(bookings, admin, bookings.apply(admin, booking_id, action, reason))
