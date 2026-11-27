from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import ConflictError
from app.core.messages import DealMessages, OrderMessages
from app.models.deal import Deal
from app.models.notification import NotificationType
from app.models.order import BUSINESS_CANCELLABLE_STATUSES, Order, OrderStatus, PaymentMethod
from app.models.payment_status import PaymentStatus
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.deal import DealRead
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.deal_expiry_service import DealExpiryService
from app.services.notification_service import NotificationService
from app.services.order_cancellation import OrderCancellation

ENTITY_TYPE = "deal"
PAYMENT_IN_PROGRESS_STATUSES = (OrderStatus.AWAITING_PAYMENT,)


@dataclass(frozen=True)
class CancelledOrder:
    order_id: UUID
    order_number: str
    customer_id: UUID
    refund_amount: str | None


def _refund_amount(order: Order) -> str | None:
    payment = order.payment
    if order.payment_method != PaymentMethod.ONLINE or payment is None:
        return None
    if payment.status != PaymentStatus.PAID:
        return None
    return f"{payment.total_amount} {payment.currency}"


class DealCancellationService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._participants = DealParticipantRepository(db)
        self._orders = OrderRepository(db)
        self._order_cancellation = OrderCancellation(db, registry)
        self._access = DealAccessPolicy(db)
        self._expiry = DealExpiryService(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def cancel(self, deal_id: UUID, actor: User) -> DealRead:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, actor)
        previous_status = deal.status
        if not self._deals.cancel(deal.id):
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_CANCELLABLE)
        if self._orders.list_ids_for_deal(deal.id, PAYMENT_IN_PROGRESS_STATUSES):
            self._db.rollback()
            raise ConflictError(DealMessages.PAYMENT_IN_PROGRESS)
        self._invitations.close_open([deal.id])
        self._db.commit()
        cancelled_orders = self._cancel_open_orders(deal.id, actor)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DEAL_CANCELLED,
            entity_type=ENTITY_TYPE,
            entity_id=deal.id,
            metadata={
                "previous_status": previous_status.value,
                "cancelled_orders": [order.order_number for order in cancelled_orders],
                "refund_due_orders": [
                    order.order_number for order in cancelled_orders if order.refund_amount
                ],
            },
        )
        self._notify(deal, actor, cancelled_orders)
        return DealRead.from_deal(get_deal(self._deals, deal.id), actor)

    def _cancel_open_orders(self, deal_id: UUID, actor: User) -> list[CancelledOrder]:
        order_ids = self._orders.list_ids_for_deal(deal_id, BUSINESS_CANCELLABLE_STATUSES)
        cancelled: list[CancelledOrder] = []
        for order_id in order_ids:
            order = self._orders.get(order_id, for_update=True)
            if order is None or order.status not in BUSINESS_CANCELLABLE_STATUSES:
                self._db.rollback()
                continue
            self._order_cancellation.cancel(
                order, actor, OrderMessages.DEAL_CANCELLED_REASON, BUSINESS_CANCELLABLE_STATUSES
            )
            cancelled.append(
                CancelledOrder(
                    order_id=order.id,
                    order_number=order.order_number,
                    customer_id=order.customer_id,
                    refund_amount=_refund_amount(order),
                )
            )
        return cancelled

    def _notify(self, deal: Deal, actor: User, cancelled_orders: list[CancelledOrder]) -> None:
        buyers = {order.customer_id for order in cancelled_orders}
        for order in cancelled_orders:
            self._notifications.notify_deal_order_cancelled(
                order.customer_id,
                actor,
                order.order_id,
                order.order_number,
                deal.name,
                order.refund_amount,
            )
        for user_id in self._participants.user_ids_for_deal(deal.id):
            if user_id in buyers or user_id == actor.id:
                continue
            self._notifications.notify_deal_event(
                user_id, actor, NotificationType.DEAL_CANCELLED, deal.id, deal.name
            )
