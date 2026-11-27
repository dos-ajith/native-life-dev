from collections.abc import Collection, Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.orm import Session, noload

from app.models.deal import Deal
from app.models.deal_item import DealItem
from app.models.order import Order, OrderItem, OrderStatus, PaymentMethod
from app.models.order_payment import OrderPayment
from app.models.payment_status import PaymentStatus
from app.schemas.pagination import PaginationParams

OPEN_ORDER_STATUSES = (
    OrderStatus.AWAITING_PAYMENT,
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
)


def _released() -> ColumnElement[bool]:
    return or_(
        Order.payment_method != PaymentMethod.ONLINE,
        exists().where(
            OrderPayment.order_id == Order.id, OrderPayment.status == PaymentStatus.PAID
        ),
    )


def _sold_by_individual(seller_id: UUID) -> ColumnElement[bool]:
    return and_(
        Order.business_id.is_(None),
        Order.deal_id.in_(select(Deal.id).where(Deal.created_by == seller_id)),
    )


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, order: Order) -> Order:
        self._db.add(order)
        self._db.flush()
        return order

    def get_many_for_business(self, business_id: UUID, order_ids: Collection[UUID]) -> list[Order]:
        return list(
            self._db.scalars(
                select(Order)
                .options(noload(Order.items))
                .where(Order.business_id == business_id, Order.id.in_(order_ids))
            )
        )

    def has_open_for_address(self, address_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    exists().where(
                        Order.shipping_address_id == address_id,
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                )
            )
        )

    def get(self, order_id: UUID, for_update: bool = False) -> Order | None:
        query = select(Order).where(Order.id == order_id)
        if for_update:
            query = query.with_for_update()
        return self._db.scalar(query.execution_options(populate_existing=True))

    def list_for_customer(
        self, customer_id: UUID, status: OrderStatus | None, params: PaginationParams
    ) -> tuple[list[Order], int]:
        return self._list(Order.customer_id == customer_id, status, params)

    def list_for_business(
        self, business_id: UUID, status: OrderStatus | None, params: PaginationParams
    ) -> tuple[list[Order], int]:
        return self._list(Order.business_id == business_id, status, params)

    def list_for_individual_seller(
        self, seller_id: UUID, status: OrderStatus | None, params: PaginationParams
    ) -> tuple[list[Order], int]:
        return self._list(_sold_by_individual(seller_id), status, params)

    def get_sold_by_individual(
        self, order_id: UUID, seller_id: UUID, for_update: bool = False
    ) -> Order | None:
        query = select(Order).where(
            Order.id == order_id, _sold_by_individual(seller_id), _released()
        )
        if for_update:
            query = query.with_for_update()
        return self._db.scalar(query.execution_options(populate_existing=True))

    def customer_has_open_order_in_deal(self, customer_id: UUID, deal_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    exists().where(
                        Order.customer_id == customer_id,
                        Order.deal_id == deal_id,
                        Order.status != OrderStatus.CANCELLED,
                    )
                )
            )
        )

    def list_ids_for_deal(self, deal_id: UUID, statuses: Collection[OrderStatus]) -> list[UUID]:
        return list(
            self._db.scalars(
                select(Order.id)
                .where(Order.deal_id == deal_id, Order.status.in_(statuses))
                .order_by(Order.created_at, Order.id)
            )
        )

    def deal_item_has_orders(self, deal_item_id: UUID) -> bool:
        return bool(self._db.scalar(select(exists().where(OrderItem.deal_item_id == deal_item_id))))

    def lock_deal_items(self, item_ids: Sequence[UUID]) -> None:
        self._db.execute(
            select(DealItem.id)
            .where(DealItem.id.in_(item_ids))
            .order_by(DealItem.id)
            .with_for_update()
        ).all()

    def deal_item_ordered_quantity(self, deal_item_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.coalesce(func.sum(OrderItem.quantity), 0))
                .join(Order, Order.id == OrderItem.order_id)
                .where(
                    OrderItem.deal_item_id == deal_item_id,
                    Order.status != OrderStatus.CANCELLED,
                )
            )
            or 0
        )

    def _list(
        self,
        owner_filter: ColumnElement[bool],
        status: OrderStatus | None,
        params: PaginationParams,
    ) -> tuple[list[Order], int]:
        filters = [owner_filter, _released()]
        if status is not None:
            filters.append(Order.status == status)
        total = self._db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
        orders = self._db.scalars(
            select(Order)
            .where(*filters)
            .order_by(Order.created_at.desc(), Order.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return list(orders), total
