from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.order_repository import OrderRepository


@dataclass(frozen=True)
class OrderSummary:
    id: UUID
    order_number: str
    status: str
    customer_name: str
    total_amount: Decimal
    currency: str
    created_at: datetime


def find_order_summaries(
    db: Session, business_id: UUID, order_ids: Collection[UUID]
) -> dict[UUID, OrderSummary]:
    if not order_ids:
        return {}
    return {
        order.id: OrderSummary(
            id=order.id,
            order_number=order.order_number,
            status=order.status.value,
            customer_name=order.customer_name,
            total_amount=order.total_amount,
            currency=order.currency,
            created_at=order.created_at,
        )
        for order in OrderRepository(db).get_many_for_business(business_id, order_ids)
    }
