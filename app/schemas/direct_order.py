from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.deal_order import MAX_ORDER_LINE_QUANTITY, OrderDetails

MAX_DIRECT_ORDER_ITEMS = 50


class DirectOrderLineCreate(BaseModel):
    product_id: UUID
    quantity: Annotated[int, Field(ge=1, le=MAX_ORDER_LINE_QUANTITY)]


class DirectOrderCreate(OrderDetails):
    items: Annotated[
        list[DirectOrderLineCreate], Field(min_length=1, max_length=MAX_DIRECT_ORDER_ITEMS)
    ]
