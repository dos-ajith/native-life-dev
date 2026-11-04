from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.order import DeliveryOption, PaymentMethod
from app.schemas.deal import MAX_DEAL_ITEMS
from app.schemas.validators import NonBlankStr

MAX_ORDER_LINE_QUANTITY = 100000
CustomerName = Annotated[NonBlankStr, Field(max_length=150)]
CustomerPhone = Annotated[NonBlankStr, Field(max_length=30)]
OrderNotes = Annotated[NonBlankStr, Field(max_length=1000)]


class DealOrderLineCreate(BaseModel):
    deal_item_id: UUID
    quantity: Annotated[int, Field(ge=1, le=MAX_ORDER_LINE_QUANTITY)]


class OrderDetails(BaseModel):
    customer_name: CustomerName
    delivery_option: DeliveryOption
    payment_method: PaymentMethod = PaymentMethod.CASH_ON_DELIVERY
    customer_phone: CustomerPhone | None = None
    address_id: UUID | None = None
    route_id: UUID | None = None
    notes: OrderNotes | None = None


class DealOrderCreate(OrderDetails):
    items: Annotated[list[DealOrderLineCreate], Field(min_length=1, max_length=MAX_DEAL_ITEMS)]
