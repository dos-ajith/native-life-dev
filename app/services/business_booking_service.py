from collections.abc import Collection
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AppError, AuthorizationError, ConflictError, NotFoundError
from app.core.messages import BookingMessages
from app.core.payments import PaymentGateway
from app.core.timezone import app_now
from app.models.booking import (
    OWNER_CANCELLABLE_STATUSES,
    OWNER_COMPLETABLE_STATUSES,
    OWNER_DECIDABLE_STATUSES,
    Booking,
    BookingStatus,
)
from app.models.business import Business
from app.models.notification import NotificationType
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.schemas.booking import BookingCancel, BookingRead, BookingReject
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.booking_notifier import BookingNotifier
from app.services.booking_payment_service import BookingPaymentService
from app.services.business_service import BusinessService
from app.services.earning_ledger import EarningLedger

ENTITY_TYPE = "booking"


class BusinessBookingService:
    def __init__(self, db: Session, gateway: PaymentGateway | None = None) -> None:
        self._db = db
        self._payments = BookingPaymentService(db, gateway)
        self._bookings = BookingRepository(db)
        self._businesses = BusinessService(db)
        self._notifier = BookingNotifier(db)
        self._activity_logs = ActivityLogService(db)
        self._earnings = EarningLedger(db)

    def list_bookings(
        self,
        business_id: UUID,
        status: BookingStatus | None,
        params: PaginationParams,
        actor: User,
    ) -> tuple[list[BookingRead], int]:
        business = self._businesses.get_for_actor(business_id, actor)
        bookings, total = self._bookings.list_for_business(business.id, status, params)
        return [BookingRead.from_booking(item) for item in bookings], total

    def get(self, business_id: UUID, booking_id: UUID, actor: User) -> BookingRead:
        business = self._businesses.get_for_actor(business_id, actor)
        return BookingRead.from_booking(self._booking_of(business, booking_id))

    def confirm(self, business_id: UUID, booking_id: UUID, actor: User) -> BookingRead:
        business = self._owned_business(business_id, actor)
        booking = self._booking_of(business, booking_id)
        self._move(
            booking,
            actor,
            OWNER_DECIDABLE_STATUSES,
            BookingStatus.CONFIRMED,
            None,
            BookingMessages.NOT_REQUESTED,
        )
        try:
            payment = self._payments.open_link(booking)
        except AppError:
            self._db.rollback()
            raise
        self._db.commit()
        saved = self._booking_of(business, booking_id)
        self._log(actor, ActivityAction.BOOKING_CONFIRMED, saved)
        if payment is not None:
            self._payments.log_link_created(actor, payment)
        self._notifier.responded(
            saved, saved.customer_id, actor, NotificationType.BOOKING_CONFIRMED, None
        )
        return BookingRead.from_booking(saved)

    def reject(
        self, business_id: UUID, booking_id: UUID, payload: BookingReject, actor: User
    ) -> BookingRead:
        return self._respond(
            business_id,
            booking_id,
            actor,
            OWNER_DECIDABLE_STATUSES,
            BookingStatus.REJECTED,
            payload.note,
            ActivityAction.BOOKING_REJECTED,
            NotificationType.BOOKING_REJECTED,
            BookingMessages.NOT_REQUESTED,
        )

    def cancel(
        self, business_id: UUID, booking_id: UUID, payload: BookingCancel, actor: User
    ) -> BookingRead:
        return self._respond(
            business_id,
            booking_id,
            actor,
            OWNER_CANCELLABLE_STATUSES,
            BookingStatus.CANCELLED,
            payload.reason,
            ActivityAction.BOOKING_CANCELLED,
            NotificationType.BOOKING_CANCELLED,
            BookingMessages.NOT_CONFIRMED,
        )

    def complete(self, business_id: UUID, booking_id: UUID, actor: User) -> BookingRead:
        return self._respond(
            business_id,
            booking_id,
            actor,
            OWNER_COMPLETABLE_STATUSES,
            BookingStatus.COMPLETED,
            None,
            ActivityAction.BOOKING_COMPLETED,
            NotificationType.BOOKING_COMPLETED,
            BookingMessages.NOT_CONFIRMED,
        )

    def _respond(
        self,
        business_id: UUID,
        booking_id: UUID,
        actor: User,
        allowed: Collection[BookingStatus],
        target: BookingStatus,
        note: str | None,
        action: str,
        notification: NotificationType,
        conflict_message: str,
    ) -> BookingRead:
        business = self._owned_business(business_id, actor)
        booking = self._booking_of(business, booking_id)
        self._move(booking, actor, allowed, target, note, conflict_message)
        self._db.commit()
        saved = self._booking_of(business, booking_id)
        self._log(actor, action, saved)
        self._earnings.sync_booking(saved.id, actor)
        self._notifier.responded(saved, saved.customer_id, actor, notification, note)
        return BookingRead.from_booking(saved)

    def _owned_business(self, business_id: UUID, actor: User) -> Business:
        business = self._businesses.get(business_id)
        if business.owner_id != actor.id:
            raise AuthorizationError(BookingMessages.NOT_BUSINESS_OWNER)
        return business

    def _move(
        self,
        booking: Booking,
        actor: User,
        allowed: Collection[BookingStatus],
        target: BookingStatus,
        note: str | None,
        conflict_message: str,
    ) -> None:
        moved = self._bookings.transition(booking.id, allowed, target, actor.id, note, app_now())
        if not moved:
            self._db.rollback()
            raise ConflictError(conflict_message)

    def _log(self, actor: User, action: str, booking: Booking) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=booking.id,
            metadata={
                "business_id": str(booking.business_id),
                "booking_number": booking.booking_number,
            },
        )

    def _booking_of(self, business: Business, booking_id: UUID) -> Booking:
        booking = self._bookings.get(booking_id)
        if booking is None or booking.business_id != business.id:
            raise NotFoundError(BookingMessages.NOT_FOUND)
        return booking
