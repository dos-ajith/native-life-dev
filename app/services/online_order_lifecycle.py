from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.models.order import Order, OrderStatus, OrderType
from app.plugins.registry import PluginRegistry
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_cart_repository import ProductCartRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService
from app.services.delivery_request_service import DeliveryRequestService
from app.services.earning_ledger import EarningLedger
from app.services.order_cancellation import OrderCancellation

ENTITY_TYPE = "order"


class OnlineOrderLifecycle:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._orders = OrderRepository(db)
        self._carts = CartRepository(db)
        self._product_carts = ProductCartRepository(db)
        self._users = UserRepository(db)
        self._delivery_requests = DeliveryRequestService(db)
        self._cancellation = OrderCancellation(db, registry)
        self._activity_logs = ActivityLogService(db)
        self._earnings = EarningLedger(db)

    def release(self, order_id: UUID) -> None:
        order = self._awaiting(order_id)
        if order is None:
            return
        order.status = OrderStatus.PENDING
        self._remove_from_cart(order)
        released = self._delivery_requests.release_held(order)
        self._db.commit()
        customer = self._users.get_by_id(order.customer_id)
        self._activity_logs.log(
            actor=customer,
            action=ActivityAction.ORDER_PLACED,
            entity_type=ENTITY_TYPE,
            entity_id=order.id,
            metadata={
                "order_number": order.order_number,
                "item_count": len(order.items),
                "total_amount": str(order.total_amount),
                "payment_method": order.payment_method.value,
            },
        )
        self._earnings.sync_order(order.id, customer)
        if customer is None:
            return
        for request in released:
            self._delivery_requests.announce_released(request, order, customer)

    def discard(self, order_id: UUID, reason: str) -> None:
        order = self._awaiting(order_id)
        if order is None:
            return
        self._cancellation.discard_unpaid(order, order.customer_id, reason)

    def _awaiting(self, order_id: UUID) -> Order | None:
        order = self._orders.get(order_id, for_update=True)
        if order is None or order.status != OrderStatus.AWAITING_PAYMENT:
            self._db.rollback()
            return None
        return order

    def _remove_from_cart(self, order: Order) -> None:
        if order.order_type == OrderType.DEAL:
            deal_item_ids = [item.deal_item_id for item in order.items if item.deal_item_id]
            self._carts.remove_deal_items(order.customer_id, deal_item_ids)
            return
        if order.business_id is None:
            return
        product_ids = [item.product_id for item in order.items if item.product_id]
        self._product_carts.remove_products(order.customer_id, order.business_id, product_ids)
