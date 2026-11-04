from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.plugins.sdk import BaseReadSchema

from ..config import MAX_STOCK_QUANTITY, NOTE_MAX_LENGTH
from ..messages import EcommerceMessages


class AdjustmentReason(StrEnum):
    RESTOCK = "restock"
    CORRECTION = "correction"
    DAMAGE = "damage"
    RETURN = "return"
    OTHER = "other"


class StockAdjustmentCreate(BaseModel):
    reason: AdjustmentReason
    change: Annotated[int, Field(ge=-MAX_STOCK_QUANTITY, le=MAX_STOCK_QUANTITY)]
    note: Annotated[str, Field(max_length=NOTE_MAX_LENGTH)] | None = None

    @field_validator("change")
    @classmethod
    def change_is_not_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError(EcommerceMessages.STOCK_CHANGE_ZERO)
        return value


class StockThresholdUpdate(BaseModel):
    low_stock_threshold: Annotated[int, Field(ge=0, le=MAX_STOCK_QUANTITY)] | None = None


class StockLevelRead(BaseReadSchema):
    product_id: UUID
    product_name: str
    sku: str
    quantity: int
    low_stock_threshold: int | None
    effective_low_stock_threshold: int
    is_low_stock: bool


class StockMovementRead(BaseReadSchema):
    id: UUID
    product_id: UUID
    change: int
    quantity_after: int
    reason: str
    order_id: UUID | None
    note: str | None
    created_by: UUID | None
    created_at: datetime
