import enum
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ORDER_NUMBER_LENGTH = 40
CUSTOMER_NAME_LENGTH = 150
CUSTOMER_PHONE_LENGTH = 30
CURRENCY_LENGTH = 3
CANCELLATION_REASON_LENGTH = 500
LINE_TOTAL_PRECISION = 14
PRICE_PRECISION = 12
PRICE_SCALE = 2
TAX_PERCENT_PRECISION = 5


class OrderStatus(enum.StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


ORDER_TRANSITIONS = {
    OrderStatus.PENDING: frozenset({OrderStatus.CONFIRMED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.SHIPPED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}
BUSINESS_CANCELLABLE_STATUSES = frozenset({OrderStatus.PENDING, OrderStatus.CONFIRMED})
CUSTOMER_CANCELLABLE_STATUSES = frozenset({OrderStatus.PENDING})


class OrderType(enum.StrEnum):
    DEAL = "deal"
    DIRECT = "direct"


class PaymentMethod(enum.StrEnum):
    CASH_ON_DELIVERY = "cash_on_delivery"


ORDER_NUMBER_SEQUENCE = Sequence("order_number_seq", start=2001, metadata=Base.metadata)


class DeliveryOption(enum.StrEnum):
    INSTANT = "instant"
    ROUTE = "route"
    SELF_PICKUP = "self_pickup"


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_deal_item_id", "deal_item_id"),)

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    deal_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("deal_items.id", ondelete="RESTRICT"), default=None
    )
    product_id: Mapped[UUID | None] = mapped_column(default=None)
    product_name: Mapped[str] = mapped_column(String(255))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    quantity: Mapped[int] = mapped_column(Integer())
    line_total: Mapped[Decimal] = mapped_column(Numeric(LINE_TOTAL_PRECISION, PRICE_SCALE))
    tax_percent: Mapped[Decimal] = mapped_column(
        Numeric(TAX_PERCENT_PRECISION, PRICE_SCALE), server_default=text("0"), default=Decimal(0)
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(LINE_TOTAL_PRECISION, PRICE_SCALE), server_default=text("0"), default=Decimal(0)
    )


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "(order_type = 'deal') = (deal_id IS NOT NULL)", name="ck_orders_deal_id_matches_type"
        ),
        CheckConstraint(
            "business_id IS NOT NULL OR order_type = 'deal'",
            name="ck_orders_business_required_unless_deal",
        ),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_business_id", "business_id"),
    )

    order_number: Mapped[str] = mapped_column(String(ORDER_NUMBER_LENGTH), unique=True)
    deal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("deals.id", ondelete="RESTRICT"), default=None
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(
            OrderType,
            name="order_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    business_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), default=None
    )
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    promoter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    delivery_option: Mapped[DeliveryOption | None] = mapped_column(
        Enum(
            DeliveryOption,
            name="delivery_option",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=None,
    )
    delivery_fee: Mapped[Decimal] = mapped_column(
        Numeric(LINE_TOTAL_PRECISION, PRICE_SCALE), server_default=text("0"), default=Decimal(0)
    )
    expected_delivery_date: Mapped[date | None] = mapped_column(default=None)
    expected_delivery_from: Mapped[time | None] = mapped_column(default=None)
    expected_delivery_to: Mapped[time | None] = mapped_column(default=None)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(
            PaymentMethod,
            name="payment_method",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        server_default=PaymentMethod.CASH_ON_DELIVERY.value,
        default=PaymentMethod.CASH_ON_DELIVERY,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="order_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=OrderStatus.PENDING,
    )
    customer_name: Mapped[str] = mapped_column(String(CUSTOMER_NAME_LENGTH))
    customer_phone: Mapped[str | None] = mapped_column(String(CUSTOMER_PHONE_LENGTH), default=None)
    shipping_address: Mapped[str | None] = mapped_column(Text(), default=None)
    shipping_location: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), default=None
    )
    shipping_village_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gis_villages.id", ondelete="RESTRICT"), default=None
    )
    shipping_address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_addresses.id", ondelete="SET NULL"), default=None
    )
    notes: Mapped[str | None] = mapped_column(Text(), default=None)
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(LINE_TOTAL_PRECISION, PRICE_SCALE), server_default=text("0"), default=Decimal(0)
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(LINE_TOTAL_PRECISION, PRICE_SCALE))
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(CANCELLATION_REASON_LENGTH), default=None
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(default=None)

    items: Mapped[list[OrderItem]] = relationship(
        order_by="OrderItem.created_at",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def shipping_latitude(self) -> float | None:
        return (
            float(to_shape(self.shipping_location).y)
            if self.shipping_location is not None
            else None
        )

    @property
    def shipping_longitude(self) -> float | None:
        return (
            float(to_shape(self.shipping_location).x)
            if self.shipping_location is not None
            else None
        )
