from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import OrderMessages
from app.models.order import BUSINESS_CANCELLABLE_STATUSES, Order, OrderStatus
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderCancel, OrderRead, OrderStatusUpdate
from app.schemas.pagination import PaginationParams
from app.services.order_cancellation import OrderCancellation
from app.services.order_fulfilment import OrderFulfilment


class SellerOrderService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._orders = OrderRepository(db)
        self._cancellation = OrderCancellation(db, registry)
        self._fulfilment = OrderFulfilment(db)

    def list_orders(
        self, status: OrderStatus | None, params: PaginationParams, actor: User
    ) -> tuple[list[OrderRead], int]:
        orders, total = self._orders.list_for_individual_seller(actor.id, status, params)
        return [OrderRead.from_order(order) for order in orders], total

    def get(self, order_id: UUID, actor: User) -> OrderRead:
        return OrderRead.from_order(self._order_of(order_id, actor))

    def update_status(self, order_id: UUID, payload: OrderStatusUpdate, actor: User) -> OrderRead:
        order = self._order_of(order_id, actor, for_update=True)
        return OrderRead.from_order(self._fulfilment.change_status(order, payload.status, actor))

    def cancel(self, order_id: UUID, payload: OrderCancel, actor: User) -> OrderRead:
        order = self._order_of(order_id, actor, for_update=True)
        cancelled = self._cancellation.cancel(
            order, actor, payload.reason, BUSINESS_CANCELLABLE_STATUSES
        )
        return OrderRead.from_order(cancelled)

    def _order_of(self, order_id: UUID, actor: User, for_update: bool = False) -> Order:
        order = self._orders.get_sold_by_individual(order_id, actor.id, for_update)
        if order is None:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return order
