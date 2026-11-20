from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, PaymentGatewayDep
from app.core.messages import BookingMessages, PaymentMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.booking import BookingCancel, BookingCreate, BookingListQuery, BookingRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.booking_payment_service import BookingPaymentService
from app.services.booking_service import BookingService

router = APIRouter(prefix="/me/bookings", tags=[ApiTag.BOOKINGS])
place_router = APIRouter(prefix="/businesses/{business_id}/bookings", tags=[ApiTag.BOOKINGS])


@place_router.post(
    "", response_model=SuccessResponse[BookingRead], status_code=status.HTTP_201_CREATED
)
def place_booking(
    business_id: UUID,
    payload: BookingCreate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
    background_tasks: BackgroundTasks,
) -> SuccessResponse[BookingRead]:
    booking = BookingService(db, registry).place(
        business_id, payload, current_user, background_tasks
    )
    return SuccessResponse(message=BookingMessages.PLACED, data=booking)


@router.get("", response_model=SuccessResponse[Page[BookingRead]])
def list_my_bookings(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[BookingListQuery, Query()],
) -> SuccessResponse[Page[BookingRead]]:
    bookings, total = BookingService(db).list_mine(current_user, query.status, params)
    return SuccessResponse(
        message=BookingMessages.LIST_RETRIEVED,
        data=Page[BookingRead].create(items=bookings, total=total, params=params),
    )


@router.get("/{booking_id}", response_model=SuccessResponse[BookingRead])
def get_my_booking(
    booking_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[BookingRead]:
    return SuccessResponse(
        message=BookingMessages.RETRIEVED,
        data=BookingService(db).get_mine(booking_id, current_user),
    )


@router.post("/{booking_id}/cancel", response_model=SuccessResponse[BookingRead])
def cancel_my_booking(
    booking_id: UUID,
    payload: BookingCancel,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[BookingRead]:
    booking = BookingService(db).cancel_mine(booking_id, payload, current_user)
    return SuccessResponse(message=BookingMessages.CANCELLED, data=booking)


@router.post(
    "/{booking_id}/payment/sync",
    response_model=SuccessResponse[BookingRead],
    tags=[ApiTag.PAYMENTS],
)
def sync_my_booking_payment(
    booking_id: UUID,
    db: DbSessionDep,
    gateway: PaymentGatewayDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[BookingRead]:
    booking = BookingPaymentService(db, gateway).sync_for_customer(booking_id, current_user)
    return SuccessResponse(message=PaymentMessages.STATUS_RETRIEVED, data=booking)
