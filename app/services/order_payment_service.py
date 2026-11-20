import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    BusinessRuleError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.messages import OrderMessages, PaymentMessages
from app.core.payments import PaymentGateway, PaymentLinkRequest
from app.core.timezone import app_now, to_naive_app_time
from app.models.order import Order, PaymentMethod
from app.models.order_payment import OrderPayment
from app.models.payment_status import PaymentStatus
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.order_payment_repository import OrderPaymentRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderRead
from app.schemas.payment import PaymentStatusRead
from app.services.activity_log_service import ActivityLogService
from app.services.online_order_lifecycle import OnlineOrderLifecycle
from app.services.payment_links import link_expires_at, minor_units, settled_status

logger = logging.getLogger(__name__)

ENTITY_TYPE = "order_payment"
EXPIRY_GRACE = timedelta(minutes=2)
SETTLED_ACTIONS = {
    PaymentStatus.PAID: ActivityAction.ORDER_PAYMENT_PAID,
    PaymentStatus.EXPIRED: ActivityAction.ORDER_PAYMENT_EXPIRED,
    PaymentStatus.CANCELLED: ActivityAction.ORDER_PAYMENT_CANCELLED,
}


def ensure_payment_method_available(method: PaymentMethod) -> None:
    if method == PaymentMethod.ONLINE and get_settings().payment_provider == "disabled":
        raise BusinessRuleError(PaymentMessages.GATEWAY_DISABLED)


def is_released(order: Order) -> bool:
    if order.payment_method != PaymentMethod.ONLINE:
        return True
    return order.payment is not None and order.payment.status == PaymentStatus.PAID


def ensure_paid_if_online(order: Order) -> None:
    if order.payment_method != PaymentMethod.ONLINE:
        return
    if order.payment is None or order.payment.status != PaymentStatus.PAID:
        raise BusinessRuleError(OrderMessages.PAYMENT_REQUIRED)


class OrderPaymentService:
    def __init__(
        self,
        db: Session,
        gateway: PaymentGateway | None,
        registry: PluginRegistry | None = None,
    ) -> None:
        self._db = db
        self._gateway = gateway
        self._payments = OrderPaymentRepository(db)
        self._orders = OrderRepository(db)
        self._lifecycle = OnlineOrderLifecycle(db, registry)
        self._activity_logs = ActivityLogService(db)

    def open_link(self, order: Order) -> OrderPayment | None:
        if order.payment_method != PaymentMethod.ONLINE or order.total_amount <= 0:
            return None
        gateway = self._require_gateway()
        expires_at = link_expires_at(get_settings().order_payment_expire_minutes)
        link = gateway.create_link(
            PaymentLinkRequest(
                reference=order.order_number,
                amount_minor=minor_units(order.total_amount),
                currency=order.currency,
                description=PaymentMessages.ORDER_LINK_DESCRIPTION.format(
                    order_number=order.order_number,
                    items_total=order.total_amount - order.delivery_fee,
                    tax_amount=order.tax_amount,
                    delivery_fee=order.delivery_fee,
                ),
                customer_name=order.customer_name,
                customer_phone=order.customer_phone or "",
                expires_at=expires_at,
                notes={"order_id": str(order.id), "order_number": order.order_number},
            )
        )
        return self._payments.add(
            OrderPayment(
                order_id=order.id,
                provider=gateway.name,
                provider_link_id=link.link_id,
                payment_url=link.url,
                total_amount=order.total_amount,
                currency=order.currency,
                expires_at=expires_at,
                status=PaymentStatus.PENDING,
            )
        )

    def open_link_or_rollback(self, order: Order) -> OrderPayment | None:
        try:
            return self.open_link(order)
        except AppError:
            self._db.rollback()
            raise

    def expire_overdue_holds(self) -> None:
        cutoff = to_naive_app_time(app_now()) - EXPIRY_GRACE
        for payment in self._payments.list_overdue_holds(cutoff):
            self._settle(payment, self._remote_status(payment), None, None)

    def _remote_status(self, payment: OrderPayment) -> str:
        if self._gateway is None:
            return PaymentStatus.EXPIRED.value
        try:
            state = self._gateway.fetch_link(payment.provider_link_id)
        except AppError:
            logger.warning("Could not check overdue payment link %s", payment.provider_link_id)
            return PaymentStatus.PENDING.value
        return state.status if state.status == PaymentStatus.PAID.value else "expired"

    def log_link_created(self, actor: User, payment: OrderPayment) -> None:
        self._log(actor, ActivityAction.ORDER_PAYMENT_LINK_CREATED, payment)

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
        return PaymentStatusRead.from_order_payment(settled)

    def sync_for_customer(self, order_id: UUID, actor: User) -> OrderRead:
        self.expire_overdue_holds()
        order = self._own_order(order_id, actor)
        payment = order.payment
        if payment is None:
            raise NotFoundError(PaymentMessages.NO_PAYMENT)
        if payment.status == PaymentStatus.PENDING:
            state = self._require_gateway().fetch_link(payment.provider_link_id)
            self._settle(payment, state.status, state.payment_id, actor)
        return OrderRead.from_order(self._own_order(order_id, actor))

    def _settle(
        self,
        payment: OrderPayment,
        gateway_status: str,
        provider_payment_id: str | None,
        actor: User | None,
    ) -> OrderPayment:
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
            self._lifecycle.release(saved.order_id)
        else:
            self._lifecycle.discard(saved.order_id, OrderMessages.PAYMENT_NOT_COMPLETED)
        return self._reload(saved)

    def _own_order(self, order_id: UUID, actor: User) -> Order:
        order = self._orders.get(order_id)
        if order is None or order.customer_id != actor.id:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return order

    def _reload(self, payment: OrderPayment) -> OrderPayment:
        saved = self._payments.get_by_link_id(payment.provider_link_id)
        if saved is None:
            raise NotFoundError(PaymentMessages.NO_PAYMENT)
        return saved

    def _require_gateway(self) -> PaymentGateway:
        if self._gateway is None:
            raise ServiceUnavailableError(PaymentMessages.GATEWAY_DISABLED)
        return self._gateway

    def _log(self, actor: User | None, action: str, payment: OrderPayment) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=payment.id,
            metadata={
                "order_id": str(payment.order_id),
                "status": payment.status.value,
                "total_amount": str(payment.total_amount),
            },
        )
