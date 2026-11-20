import uuid
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import BookingMessages
from app.core.timezone import app_now
from app.models.booking import CUSTOMER_CANCELLABLE_STATUSES, Booking, BookingStatus
from app.models.business import BusinessStatus
from app.models.notification import NotificationType
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.booking_repository import BookingRepository
from app.repositories.business_repository import BusinessRepository
from app.schemas.booking import BookingCancel, BookingCreate, BookingRead
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.booking_charges import booking_charges
from app.services.booking_notifier import BookingNotifier
from app.services.booking_provider_resolver import BookingProviderResolver
from app.services.earning_ledger import EarningLedger
from app.services.finance_settings_service import (
    FeeKind,
    FinanceSettingsService,
    snapshot_charges,
)

ENTITY_TYPE = "booking"
BOOKING_NUMBER_PREFIX = "BK"
BOOKING_NUMBER_HEX_LENGTH = 8


def new_booking_number() -> str:
    return f"{BOOKING_NUMBER_PREFIX}{uuid.uuid4().hex[:BOOKING_NUMBER_HEX_LENGTH].upper()}"


class BookingService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._bookings = BookingRepository(db)
        self._businesses = BusinessRepository(db)
        self._providers = BookingProviderResolver(db, registry)
        self._notifier = BookingNotifier(db)
        self._finance = FinanceSettingsService(db)
        self._earnings = EarningLedger(db)
        self._activity_logs = ActivityLogService(db)

    def place(
        self,
        business_id: UUID,
        payload: BookingCreate,
        actor: User,
        background_tasks: BackgroundTasks,
    ) -> BookingRead:
        business = self._businesses.get_by_id(business_id)
        if business is None or business.status != BusinessStatus.ACTIVE:
            raise BusinessRuleError(BookingMessages.BUSINESS_NOT_ACTIVE)
        if business.owner_id == actor.id:
            raise BusinessRuleError(BookingMessages.OWN_BUSINESS)
        if payload.start_date < app_now().date():
            raise BusinessRuleError(BookingMessages.START_IN_PAST)
        resolved = self._providers.provider_for(business.id)
        item = resolved.provider.find_bookable(self._db, business.id, payload.item_id)
        if item is None or not item.is_active:
            raise BusinessRuleError(BookingMessages.ITEM_UNAVAILABLE)
        booking = self._bookings.add(
            Booking(
                booking_number=new_booking_number(),
                business_id=business.id,
                customer_id=actor.id,
                plugin_key=resolved.plugin_key,
                item_id=item.id,
                item_name=item.name,
                start_date=payload.start_date,
                end_date=payload.end_date,
                party_size=payload.party_size,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                note=payload.note,
                original_price=item.original_price,
                unit_price=item.price,
                tax_percent=item.tax_percent,
                currency=item.currency,
            )
        )
        snapshot_charges(
            booking, self._finance.charges_for(FeeKind.BOOKING, booking_charges(booking).subtotal)
        )
        self._db.commit()
        self._log(actor, ActivityAction.BOOKING_REQUESTED, booking)
        self._notifier.requested(booking, business.owner_id, actor, background_tasks)
        return BookingRead.from_booking(booking)

    def list_mine(
        self, actor: User, status: BookingStatus | None, params: PaginationParams
    ) -> tuple[list[BookingRead], int]:
        bookings, total = self._bookings.list_for_customer(actor.id, status, params)
        return [BookingRead.from_booking(item) for item in bookings], total

    def get_mine(self, booking_id: UUID, actor: User) -> BookingRead:
        return BookingRead.from_booking(self._own_booking(booking_id, actor))

    def cancel_mine(self, booking_id: UUID, payload: BookingCancel, actor: User) -> BookingRead:
        booking = self._own_booking(booking_id, actor)
        moved = self._bookings.transition(
            booking.id,
            CUSTOMER_CANCELLABLE_STATUSES,
            BookingStatus.CANCELLED,
            actor.id,
            payload.reason,
            app_now(),
        )
        if not moved:
            self._db.rollback()
            raise ConflictError(BookingMessages.NOT_CANCELLABLE)
        self._db.commit()
        saved = self._reload(booking.id)
        self._log(actor, ActivityAction.BOOKING_CANCELLED, saved)
        self._earnings.sync_booking(saved.id, actor)
        owner = self._businesses.get_by_id(saved.business_id)
        if owner is not None:
            self._notifier.responded(
                saved, owner.owner_id, actor, NotificationType.BOOKING_CANCELLED, payload.reason
            )
        return BookingRead.from_booking(saved)

    def _own_booking(self, booking_id: UUID, actor: User) -> Booking:
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise NotFoundError(BookingMessages.NOT_FOUND)
        if booking.customer_id != actor.id:
            raise AuthorizationError(BookingMessages.NOT_YOUR_BOOKING)
        return booking

    def _reload(self, booking_id: UUID) -> Booking:
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise NotFoundError(BookingMessages.NOT_FOUND)
        return booking

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
