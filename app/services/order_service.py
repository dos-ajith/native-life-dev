from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import OrderMessages
from app.models.order import CUSTOMER_CANCELLABLE_STATUSES, Order, OrderStatus
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderCancel, OrderRead
from app.schemas.pagination import PaginationParams
from app.services.order_cancellation import OrderCancellation


class OrderService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._orders = OrderRepository(db)
        self._cancellation = OrderCancellation(db, registry)

    def list_mine(
        self, actor: User, status: OrderStatus | None, params: PaginationParams
    ) -> tuple[list[OrderRead], int]:
        orders, total = self._orders.list_for_customer(actor.id, status, params)
        return [OrderRead.from_order(order) for order in orders], total

    def get_mine(self, order_id: UUID, actor: User) -> OrderRead:
        return OrderRead.from_order(self._own_order(order_id, actor))

    def cancel_mine(self, order_id: UUID, payload: OrderCancel, actor: User) -> OrderRead:
        self._own_order(order_id, actor)
        order = self._orders.get(order_id, for_update=True)
        if order is None:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        cancelled = self._cancellation.cancel(
            order, actor, payload.reason, CUSTOMER_CANCELLABLE_STATUSES
        )
        return OrderRead.from_order(cancelled)

    def _own_order(self, order_id: UUID, actor: User) -> Order:
        order = self._orders.get(order_id)
        if order is None or order.customer_id != actor.id:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return order
