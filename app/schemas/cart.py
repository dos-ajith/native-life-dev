from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.deal import DealStatus
from app.plugins.deal_commerce import DealProduct
from app.schemas.base import BaseReadSchema
from app.schemas.deal import deal_image_file_url
from app.schemas.deal_order import MAX_ORDER_LINE_QUANTITY, OrderDetails
from app.services.order_tax import tax_for

if TYPE_CHECKING:
    from app.models.cart_item import CartItem
    from app.models.deal import Deal
    from app.models.product_cart_item import ProductCartItem

CartQuantity = Annotated[int, Field(ge=1, le=MAX_ORDER_LINE_QUANTITY)]


class CartItemAdd(BaseModel):
    deal_item_id: UUID
    quantity: CartQuantity


class CartItemUpdate(BaseModel):
    quantity: CartQuantity


class CartCheckout(OrderDetails):
    deal_id: UUID


class CartItemRead(BaseModel):
    id: UUID
    deal_item_id: UUID
    product_id: UUID | None
    name: str
    unit: str | None
    quantity: int
    unit_price: Decimal | None
    line_total: Decimal | None

    @classmethod
    def from_cart_item(cls, cart_item: "CartItem") -> "CartItemRead":
        item = cart_item.deal_item
        return cls(
            id=cart_item.id,
            deal_item_id=item.id,
            product_id=item.product_id,
            name=item.name,
            unit=item.unit,
            quantity=cart_item.quantity,
            unit_price=item.deal_price,
            line_total=item.deal_price * cart_item.quantity
            if item.deal_price is not None
            else None,
        )


class CartDealGroupRead(BaseReadSchema):
    deal_id: UUID
    deal_name: str
    deal_status: DealStatus
    thumbnail_url: str | None
    business_id: UUID | None
    business_name: str | None
    seller_name: str
    valid_until: datetime | None
    items: list[CartItemRead]
    subtotal: Decimal

    @classmethod
    def from_lines(cls, deal: "Deal", lines: list["CartItem"]) -> "CartDealGroupRead":
        items = [CartItemRead.from_cart_item(line) for line in lines]
        thumbnail = next((image for image in deal.images if image.is_thumbnail), None)
        return cls(
            deal_id=deal.id,
            deal_name=deal.name,
            deal_status=deal.status,
            thumbnail_url=(
                deal_image_file_url(deal.id, thumbnail.id) if thumbnail is not None else None
            ),
            business_id=deal.business_id,
            business_name=deal.business.name if deal.business is not None else None,
            seller_name=(
                deal.business.name
                if deal.business is not None
                else f"{deal.creator.first_name} {deal.creator.last_name}"
            ),
            valid_until=deal.valid_until,
            items=items,
            subtotal=sum((item.line_total or Decimal(0) for item in items), Decimal(0)),
        )


class CartProductAdd(BaseModel):
    business_id: UUID
    product_id: UUID
    quantity: CartQuantity


class CartProductItemRead(BaseModel):
    id: UUID
    product_id: UUID
    name: str | None
    unit: str | None
    quantity: int
    unit_price: Decimal | None
    line_total: Decimal | None
    tax_percent: Decimal
    tax_amount: Decimal
    is_available: bool

    @classmethod
    def from_line(
        cls, line: "ProductCartItem", product: DealProduct | None
    ) -> "CartProductItemRead":
        line_total = product.selling_price * line.quantity if product is not None else None
        tax_percent = product.tax_percent if product is not None else Decimal(0)
        return cls(
            id=line.id,
            product_id=line.product_id,
            name=product.name if product is not None else None,
            unit=product.unit if product is not None else None,
            quantity=line.quantity,
            unit_price=product.selling_price if product is not None else None,
            line_total=line_total,
            tax_percent=tax_percent,
            tax_amount=tax_for(line_total, tax_percent) if line_total is not None else Decimal(0),
            is_available=product is not None and product.is_active,
        )


class CartBusinessGroupRead(BaseModel):
    business_id: UUID
    business_name: str
    items: list[CartProductItemRead]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal


class CartRead(BaseModel):
    deals: list[CartDealGroupRead]
    businesses: list[CartBusinessGroupRead]
    total_quantity: int
