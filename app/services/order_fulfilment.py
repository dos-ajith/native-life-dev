from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError
from app.core.messages import OrderMessages
from app.models.order import ORDER_TRANSITIONS, DeliveryOption, Order, OrderStatus
from app.models.user import User
from app.services.activity_log_service import ActivityLogService
from app.services.earning_ledger import EarningLedger
from app.services.order_payment_service import ensure_paid_if_online

ENTITY_TYPE = "order"
COURIER_DELIVERY_OPTIONS = frozenset({DeliveryOption.INSTANT, DeliveryOption.ROUTE})


class OrderFulfilment:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._activity_logs = ActivityLogService(db)
        self._earnings = EarningLedger(db)

    def change_status(
        self, order: Order, target: OrderStatus, actor: User, via_delivery: bool = False
    ) -> Order:
        if target == OrderStatus.CANCELLED:
            raise BusinessRuleError(OrderMessages.USE_CANCEL)
        if (
            target == OrderStatus.DELIVERED
            and not via_delivery
            and order.delivery_option in COURIER_DELIVERY_OPTIONS
        ):
            raise BusinessRuleError(OrderMessages.DELIVERED_BY_COURIER)
        current = order.status
        if target not in ORDER_TRANSITIONS[current]:
            raise BusinessRuleError(
                OrderMessages.TRANSITION_INVALID.format(current=current.value, target=target.value)
            )
        if target == OrderStatus.SHIPPED:
            ensure_paid_if_online(order)
        order.status = target
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ORDER_STATUS_CHANGED,
            entity_type=ENTITY_TYPE,
            entity_id=order.id,
            metadata={"from": current.value, "to": target.value},
        )
        self._earnings.sync_order(order.id, actor)
        return order
