from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, PaymentGatewayDep
from app.core.messages import BookingMessages
from app.core.openapi_tags import ApiTag
from app.schemas.booking import (
    BookingCancel,
    BookingListQuery,
    BookingRead,
    BookingReject,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.business_booking_service import BusinessBookingService

router = APIRouter(prefix="/me/businesses/{business_id}/bookings", tags=[ApiTag.BUSINESS_BOOKINGS])


@router.get("", response_model=SuccessResponse[Page[BookingRead]])
def list_business_bookings(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[BookingListQuery, Query()],
) -> SuccessResponse[Page[BookingRead]]:
    bookings, total = BusinessBookingService(db).list_bookings(
        business_id, query.status, params, current_user
    )
    return SuccessResponse(
        message=BookingMessages.LIST_RETRIEVED,
        data=Page[BookingRead].create(items=bookings, total=total, params=params),
    )


@router.get("/{booking_id}", response_model=SuccessResponse[BookingRead])
def get_business_booking(
    business_id: UUID, booking_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[BookingRead]:
    booking = BusinessBookingService(db).get(business_id, booking_id, current_user)
    return SuccessResponse(message=BookingMessages.RETRIEVED, data=booking)


@router.post("/{booking_id}/confirm", response_model=SuccessResponse[BookingRead])
def confirm_booking(
    business_id: UUID,
    booking_id: UUID,
    db: DbSessionDep,
    gateway: PaymentGatewayDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[BookingRead]:
    booking = BusinessBookingService(db, gateway).confirm(business_id, booking_id, current_user)
    return SuccessResponse(message=BookingMessages.CONFIRMED, data=booking)


@router.post("/{booking_id}/reject", response_model=SuccessResponse[BookingRead])
def reject_booking(
    business_id: UUID,
    booking_id: UUID,
    payload: BookingReject,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[BookingRead]:
    booking = BusinessBookingService(db).reject(business_id, booking_id, payload, current_user)
    return SuccessResponse(message=BookingMessages.REJECTED, data=booking)


@router.post("/{booking_id}/cancel", response_model=SuccessResponse[BookingRead])
def cancel_business_booking(
    business_id: UUID,
    booking_id: UUID,
    payload: BookingCancel,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[BookingRead]:
    booking = BusinessBookingService(db).cancel(business_id, booking_id, payload, current_user)
    return SuccessResponse(message=BookingMessages.CANCELLED, data=booking)


@router.post("/{booking_id}/complete", response_model=SuccessResponse[BookingRead])
def complete_booking(
    business_id: UUID, booking_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[BookingRead]:
    booking = BusinessBookingService(db).complete(business_id, booking_id, current_user)
    return SuccessResponse(message=BookingMessages.COMPLETED, data=booking)
