from collections.abc import Collection

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError
from app.core.messages import OrderMessages
from app.core.timezone import app_now, to_naive_app_time
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.plugins.deal_commerce import StockLine
from app.plugins.registry import PluginRegistry
from app.services.activity_log_service import ActivityLogService
from app.services.deal_commerce_resolver import DealCommerceResolver
from app.services.delivery_request_service import DeliveryRequestService

ENTITY_TYPE = "order"


class OrderCancellation:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._resolver = DealCommerceResolver(db, registry)
        self._delivery_requests = DeliveryRequestService(db)
        self._activity_logs = ActivityLogService(db)

    def cancel(
        self,
        order: Order,
        actor: User,
        reason: str | None,
        allowed_statuses: Collection[OrderStatus],
    ) -> Order:
        if order.status not in allowed_statuses:
            raise BusinessRuleError(
                OrderMessages.NOT_CANCELLABLE.format(current=order.status.value)
            )
        self._release_stock(order, actor)
        previous_status = order.status
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = to_naive_app_time(app_now())
        order.cancellation_reason = reason
        self._delivery_requests.cancel_for_order(order.id)
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ORDER_CANCELLED,
            entity_type=ENTITY_TYPE,
            entity_id=order.id,
            metadata={"order_number": order.order_number, "from": previous_status.value},
        )
        return order

    def _release_stock(self, order: Order, actor: User) -> None:
        if order.business_id is None:
            return
        self._resolver.provider_for(order.business_id).release_stock(
            self._db,
            order.business_id,
            order.id,
            [
                StockLine(product_id=item.product_id, quantity=item.quantity)
                for item in order.items
                if item.product_id is not None
            ],
            actor.id,
        )
