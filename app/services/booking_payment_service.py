from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, NotFoundError, ServiceUnavailableError
from app.core.messages import BookingMessages, PaymentMessages
from app.core.payments import PaymentGateway, PaymentLinkRequest
from app.core.timezone import app_now
from app.models.booking import Booking
from app.models.booking_payment import BookingPayment
from app.models.payment_status import PaymentStatus
from app.models.user import User
from app.repositories.booking_payment_repository import BookingPaymentRepository
from app.repositories.booking_repository import BookingRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.user_repository import UserRepository
from app.schemas.booking import BookingRead
from app.schemas.payment import PaymentStatusRead
from app.services.activity_log_service import ActivityLogService
from app.services.booking_charges import booking_charges
from app.services.booking_notifier import BookingNotifier
from app.services.earning_ledger import EarningLedger
from app.services.payment_links import link_expires_at, minor_units, settled_status

ENTITY_TYPE = "booking_payment"
SETTLED_ACTIONS = {
    PaymentStatus.PAID: ActivityAction.BOOKING_PAYMENT_PAID,
    PaymentStatus.EXPIRED: ActivityAction.BOOKING_PAYMENT_EXPIRED,
    PaymentStatus.CANCELLED: ActivityAction.BOOKING_PAYMENT_CANCELLED,
}


class BookingPaymentService:
    def __init__(self, db: Session, gateway: PaymentGateway | None) -> None:
        self._db = db
        self._gateway = gateway
        self._payments = BookingPaymentRepository(db)
        self._bookings = BookingRepository(db)
        self._businesses = BusinessRepository(db)
        self._users = UserRepository(db)
        self._notifier = BookingNotifier(db)
        self._activity_logs = ActivityLogService(db)
        self._earnings = EarningLedger(db)

    def open_link(self, booking: Booking) -> BookingPayment | None:
        if self._gateway is None:
            return None
        charges = booking_charges(booking)
        if charges.total_amount <= 0:
            return None
        expires_at = link_expires_at()
        link = self._gateway.create_link(
            PaymentLinkRequest(
                reference=booking.booking_number,
                amount_minor=minor_units(charges.total_amount),
                currency=booking.currency,
                description=PaymentMessages.LINK_DESCRIPTION.format(
                    item=booking.item_name,
                    party_size=charges.party_size,
                    unit_price=charges.unit_price,
                    subtotal=charges.subtotal,
                    tax_percent=charges.tax_percent,
                    tax_amount=charges.tax_amount,
                ),
                customer_name=booking.customer_name,
                customer_phone=booking.customer_phone,
                expires_at=expires_at,
                notes={"booking_id": str(booking.id), "booking_number": booking.booking_number},
            )
        )
        return self._payments.add(
            BookingPayment(
                booking_id=booking.id,
                provider=self._gateway.name,
                provider_link_id=link.link_id,
                payment_url=link.url,
                unit_price=charges.unit_price,
                party_size=charges.party_size,
                subtotal=charges.subtotal,
                tax_percent=charges.tax_percent,
                tax_amount=charges.tax_amount,
                total_amount=charges.total_amount,
                currency=booking.currency,
                expires_at=expires_at,
                status=PaymentStatus.PENDING,
            )
        )

    def log_link_created(self, actor: User, payment: BookingPayment) -> None:
        self._log(actor, ActivityAction.BOOKING_PAYMENT_LINK_CREATED, payment)

    def settle_link(
        self,
        link_id: str,
        gateway_status: str,
        provider_payment_id: str | None,
        actor: User | None,
    ) -> PaymentStatusRead | None:
        payment = self._payments.get_by_link_id(link_id)
        if payment is None:
            return None
        settled = self._settle(payment, gateway_status, provider_payment_id, actor)
        return PaymentStatusRead.from_booking_payment(settled)

    def sync_for_customer(self, booking_id: UUID, actor: User) -> BookingRead:
        booking = self._bookings.get(booking_id)
        if booking is None:
            raise NotFoundError(BookingMessages.NOT_FOUND)
        if booking.customer_id != actor.id:
            raise AuthorizationError(BookingMessages.NOT_YOUR_BOOKING)
        payment = booking.payment
        if payment is None:
            raise NotFoundError(PaymentMessages.NO_PAYMENT)
        if payment.status == PaymentStatus.PENDING:
            state = self._require_gateway().fetch_link(payment.provider_link_id)
            self._settle(payment, state.status, state.payment_id, actor)
        refreshed = self._bookings.get(booking_id)
        if refreshed is None:
            raise NotFoundError(BookingMessages.NOT_FOUND)
        return BookingRead.from_booking(refreshed)

    def _settle(
        self,
        payment: BookingPayment,
        gateway_status: str,
        provider_payment_id: str | None,
        actor: User | None,
    ) -> BookingPayment:
        target = settled_status(gateway_status)
        if target is None:
            return payment
        paid_at = app_now() if target == PaymentStatus.PAID else None
        moved = self._payments.settle_pending(payment.id, target, provider_payment_id, paid_at)
        if not moved:
            self._db.rollback()
            return self._reload(payment)
        self._db.commit()
        saved = self._reload(payment)
        self._log(actor, SETTLED_ACTIONS[target], saved)
        if target == PaymentStatus.PAID:
            self._earnings.sync_booking(saved.booking_id, actor)
            self._notify_owner_paid(saved)
        return saved

    def _notify_owner_paid(self, payment: BookingPayment) -> None:
        booking = self._bookings.get(payment.booking_id)
        if booking is None:
            return
        business = self._businesses.get_by_id(booking.business_id)
        customer = self._users.get_by_id(booking.customer_id)
        if business is None or customer is None:
            return
        self._notifier.paid(booking, business.owner_id, customer)

    def _reload(self, payment: BookingPayment) -> BookingPayment:
        saved = self._payments.get_by_link_id(payment.provider_link_id)
        if saved is None:
            raise NotFoundError(PaymentMessages.NO_PAYMENT)
        return saved

    def _require_gateway(self) -> PaymentGateway:
        if self._gateway is None:
            raise ServiceUnavailableError(PaymentMessages.GATEWAY_DISABLED)
        return self._gateway

    def _log(self, actor: User | None, action: str, payment: BookingPayment) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=payment.id,
            metadata={
                "booking_id": str(payment.booking_id),
                "status": payment.status.value,
                "total_amount": str(payment.total_amount),
            },
        )
