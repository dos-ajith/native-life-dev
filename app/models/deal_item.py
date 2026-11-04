from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.orm import Mapped, column_property, declared_attr, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.order import Order, OrderItem, OrderStatus

PRICE_PRECISION = 12
PRICE_SCALE = 2


class DealItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deal_items"
    __table_args__ = (
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_deal_items_quantity_positive"),
        CheckConstraint(
            "original_price IS NULL OR original_price >= 0",
            name="ck_deal_items_original_price_non_negative",
        ),
        CheckConstraint(
            "deal_price IS NULL OR deal_price >= 0", name="ck_deal_items_deal_price_non_negative"
        ),
        CheckConstraint(
            "original_price IS NULL OR deal_price IS NULL OR deal_price <= original_price",
            name="ck_deal_items_deal_price_within_original",
        ),
        Index("ix_deal_items_deal_id", "deal_id"),
    )

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    product_id: Mapped[UUID | None] = mapped_column(default=None)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())
    unit: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[int | None] = mapped_column(Integer())
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    deal_price: Mapped[Decimal | None] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    image_id: Mapped[UUID | None] = mapped_column(ForeignKey("deal_images.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)

    @declared_attr
    def ordered_quantity(cls) -> Mapped[int]:
        return column_property(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.deal_item_id == cls.id, Order.status != OrderStatus.CANCELLED)
            .scalar_subquery()
        )
