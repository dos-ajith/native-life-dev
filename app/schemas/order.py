from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import DeliveryOption, OrderStatus, OrderType, PaymentMethod
from app.schemas.base import BaseReadSchema
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.order import Order, OrderItem

CancellationReason = Annotated[NonBlankStr, Field(max_length=500)]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderCancel(BaseModel):
    reason: CancellationReason | None = None


class OrderListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: OrderStatus | None = None


class OrderItemRead(BaseModel):
    id: UUID
    deal_item_id: UUID | None
    product_id: UUID | None
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    @classmethod
    def from_item(cls, item: "OrderItem") -> "OrderItemRead":
        return cls(
            id=item.id,
            deal_item_id=item.deal_item_id,
            product_id=item.product_id,
            product_name=item.product_name,
            unit_price=item.unit_price,
            quantity=item.quantity,
            line_total=item.line_total,
        )


class OrderRead(BaseReadSchema):
    id: UUID
    order_number: str
    order_type: OrderType
    deal_id: UUID | None
    business_id: UUID | None
    customer_id: UUID
    promoter_id: UUID | None
    delivery_option: DeliveryOption | None
    delivery_fee: Decimal
    payment_method: PaymentMethod
    expected_delivery_date: date | None
    expected_delivery_from: time | None
    expected_delivery_to: time | None
    status: OrderStatus
    customer_name: str
    customer_phone: str | None
    shipping_address: str | None
    shipping_latitude: float | None
    shipping_longitude: float | None
    shipping_village_id: UUID | None
    notes: str | None
    currency: str
    total_amount: Decimal
    cancellation_reason: str | None
    cancelled_at: datetime | None
    items: list[OrderItemRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_order(cls, order: "Order") -> "OrderRead":
        return cls(
            id=order.id,
            order_number=order.order_number,
            order_type=order.order_type,
            deal_id=order.deal_id,
            business_id=order.business_id,
            customer_id=order.customer_id,
            promoter_id=order.promoter_id,
            delivery_option=order.delivery_option,
            delivery_fee=order.delivery_fee,
            payment_method=order.payment_method,
            expected_delivery_date=order.expected_delivery_date,
            expected_delivery_from=order.expected_delivery_from,
            expected_delivery_to=order.expected_delivery_to,
            status=order.status,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            shipping_address=order.shipping_address,
            shipping_latitude=order.shipping_latitude,
            shipping_longitude=order.shipping_longitude,
            shipping_village_id=order.shipping_village_id,
            notes=order.notes,
            currency=order.currency,
            total_amount=order.total_amount,
            cancellation_reason=order.cancellation_reason,
            cancelled_at=order.cancelled_at,
            items=[OrderItemRead.from_item(item) for item in order.items],
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
