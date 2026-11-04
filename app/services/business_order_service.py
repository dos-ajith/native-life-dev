from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import OrderMessages
from app.core.permissions import PermissionName
from app.models.business import Business
from app.models.order import BUSINESS_CANCELLABLE_STATUSES, Order, OrderStatus
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderCancel, OrderRead, OrderStatusUpdate
from app.schemas.pagination import PaginationParams
from app.services.business_service import BusinessService
from app.services.order_cancellation import OrderCancellation
from app.services.order_fulfilment import OrderFulfilment


class BusinessOrderService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._orders = OrderRepository(db)
        self._businesses = BusinessService(db)
        self._cancellation = OrderCancellation(db, registry)
        self._fulfilment = OrderFulfilment(db)

    def list_orders(
        self,
        business_id: UUID,
        status: OrderStatus | None,
        params: PaginationParams,
        actor: User,
    ) -> tuple[list[OrderRead], int]:
        business = self._businesses.get_for_actor(business_id, actor)
        orders, total = self._orders.list_for_business(business.id, status, params)
        return [OrderRead.from_order(order) for order in orders], total

    def get(self, business_id: UUID, order_id: UUID, actor: User) -> OrderRead:
        business = self._businesses.get_for_actor(business_id, actor)
        return OrderRead.from_order(self._order_of(business, order_id))

    def update_status(
        self, business_id: UUID, order_id: UUID, payload: OrderStatusUpdate, actor: User
    ) -> OrderRead:
        business = self._modifiable_business(business_id, actor)
        self._order_of(business, order_id)
        order = self._locked_order(order_id)
        return OrderRead.from_order(self._fulfilment.change_status(order, payload.status, actor))

    def cancel(
        self, business_id: UUID, order_id: UUID, payload: OrderCancel, actor: User
    ) -> OrderRead:
        business = self._modifiable_business(business_id, actor)
        self._order_of(business, order_id)
        order = self._locked_order(order_id)
        cancelled = self._cancellation.cancel(
            order, actor, payload.reason, BUSINESS_CANCELLABLE_STATUSES
        )
        return OrderRead.from_order(cancelled)

    def _modifiable_business(self, business_id: UUID, actor: User) -> Business:
        business = self._businesses.get(business_id)
        self._businesses.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        return business

    def _order_of(self, business: Business, order_id: UUID) -> Order:
        order = self._orders.get(order_id)
        if order is None or order.business_id != business.id:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return order

    def _locked_order(self, order_id: UUID) -> Order:
        order = self._orders.get(order_id, for_update=True)
        if order is None:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return order
