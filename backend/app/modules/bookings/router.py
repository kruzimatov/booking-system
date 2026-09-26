import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import ClientUser, ClockDep, CurrentUser, DbSession, SettingsDep
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreate, BookingOut
from app.modules.bookings.service import BookingService

router = APIRouter(prefix="/bookings", tags=["bookings"])


def get_booking_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> BookingService:
    return BookingService(db, clock, settings)


BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BookingOut)
def create_booking(body: BookingCreate, client: ClientUser, bookings: BookingServiceDep) -> Booking:
    return bookings.create(client, body)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: uuid.UUID, user: CurrentUser, bookings: BookingServiceDep) -> Booking:
    return bookings.get_visible(user, booking_id)
