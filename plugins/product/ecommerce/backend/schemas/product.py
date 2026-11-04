from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.plugins.sdk import BaseReadSchema

from ..config import (
    MAX_PRICE,
    MAX_STOCK_QUANTITY,
    NAME_MAX_LENGTH,
    SKU_MAX_LENGTH,
)
from ..messages import EcommerceMessages

Price = Annotated[Decimal, Field(ge=0, le=MAX_PRICE, max_digits=12, decimal_places=2)]
Sku = Annotated[str, Field(min_length=1, max_length=SKU_MAX_LENGTH, pattern=r"^[A-Za-z0-9._-]+$")]
ProductName = Annotated[str, Field(min_length=1, max_length=NAME_MAX_LENGTH)]
StockQuantity = Annotated[int, Field(ge=0, le=MAX_STOCK_QUANTITY)]


PERCENT = Decimal(100)
PERCENT_PRECISION = Decimal("0.01")


def discount_percent(selling_price: Decimal, original_price: Decimal) -> Decimal:
    if original_price <= 0 or selling_price >= original_price:
        return Decimal(0)
    return ((original_price - selling_price) / original_price * PERCENT).quantize(PERCENT_PRECISION)


class ProductCreate(BaseModel):
    name: ProductName
    description: str | None = None
    sku: Sku
    selling_price: Price
    original_price: Price | None = None
    category_id: UUID
    is_active: bool = True
    is_bulk_promotable: bool = False
    is_individually_promotable: bool = False
    quantity: StockQuantity = 0
    low_stock_threshold: StockQuantity | None = None

    @model_validator(mode="after")
    def _price_within_original(self) -> Self:
        if self.original_price is not None and self.selling_price > self.original_price:
            raise ValueError(EcommerceMessages.PRICE_ABOVE_ORIGINAL)
        return self


class ProductUpdate(BaseModel):
    name: ProductName | None = None
    description: str | None = None
    sku: Sku | None = None
    selling_price: Price | None = None
    original_price: Price | None = None
    category_id: UUID | None = None
    is_bulk_promotable: bool | None = None
    is_individually_promotable: bool | None = None


class ProductCategoryCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]


class ProductCategoryRead(BaseReadSchema):
    id: UUID
    business_id: UUID | None
    name: str
    slug: str
    is_active: bool


class ProductImageRead(BaseReadSchema):
    id: UUID
    url: str
    alt_text: str | None
    sort_order: int
    content_type: str | None
    size_bytes: int | None


class ProductStockRead(BaseReadSchema):
    quantity: int
    low_stock_threshold: int | None


class ProductRead(BaseReadSchema):
    id: UUID
    business_id: UUID
    name: str
    description: str | None
    sku: str
    selling_price: Decimal
    original_price: Decimal
    discount_percent: Decimal = Decimal(0)
    is_active: bool
    is_bulk_promotable: bool
    is_individually_promotable: bool
    category: ProductCategoryRead | None
    images: list[ProductImageRead]
    stock: ProductStockRead | None
    quantity: int = 0
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _fill_derived(self) -> Self:
        self.quantity = self.stock.quantity if self.stock is not None else 0
        self.discount_percent = discount_percent(self.selling_price, self.original_price)
        return self
