import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.booking_payment import BookingPayment

BOOKING_NUMBER_LENGTH = 20
PLUGIN_KEY_LENGTH = 64
ITEM_NAME_LENGTH = 200
CUSTOMER_NAME_LENGTH = 150
CUSTOMER_PHONE_LENGTH = 30
CURRENCY_LENGTH = 3
NOTE_LENGTH = 500
PRICE_PRECISION = 12
PRICE_SCALE = 2
TAX_PERCENT_PRECISION = 5


class BookingStatus(enum.StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


OWNER_DECIDABLE_STATUSES = frozenset({BookingStatus.REQUESTED})
OWNER_CANCELLABLE_STATUSES = frozenset({BookingStatus.CONFIRMED})
OWNER_COMPLETABLE_STATUSES = frozenset({BookingStatus.CONFIRMED})
CUSTOMER_CANCELLABLE_STATUSES = frozenset({BookingStatus.REQUESTED, BookingStatus.CONFIRMED})


class Booking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("party_size >= 1", name="ck_bookings_party_size_positive"),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_bookings_end_not_before_start"
        ),
        Index("ix_bookings_business_id_status", "business_id", "status"),
        Index("ix_bookings_customer_id", "customer_id"),
    )

    booking_number: Mapped[str] = mapped_column(String(BOOKING_NUMBER_LENGTH), unique=True)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plugin_key: Mapped[str] = mapped_column(String(PLUGIN_KEY_LENGTH))
    item_id: Mapped[UUID]
    item_name: Mapped[str] = mapped_column(String(ITEM_NAME_LENGTH))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=BookingStatus.REQUESTED,
    )
    start_date: Mapped[date] = mapped_column(Date())
    end_date: Mapped[date | None] = mapped_column(Date(), default=None)
    party_size: Mapped[int] = mapped_column(Integer())
    customer_name: Mapped[str] = mapped_column(String(CUSTOMER_NAME_LENGTH))
    customer_phone: Mapped[str] = mapped_column(String(CUSTOMER_PHONE_LENGTH))
    note: Mapped[str | None] = mapped_column(Text(), default=None)
    original_price: Mapped[Decimal | None] = mapped_column(
        Numeric(PRICE_PRECISION, PRICE_SCALE), default=None
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    tax_percent: Mapped[Decimal] = mapped_column(
        Numeric(TAX_PERCENT_PRECISION, PRICE_SCALE), server_default="0", default=Decimal(0)
    )
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    platform_fee_percent: Mapped[Decimal] = mapped_column(
        Numeric(TAX_PERCENT_PRECISION, PRICE_SCALE), server_default="0", default=Decimal(0)
    )
    platform_fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(PRICE_PRECISION, PRICE_SCALE), server_default="0", default=Decimal(0)
    )
    commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(TAX_PERCENT_PRECISION, PRICE_SCALE), server_default="0", default=Decimal(0)
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(PRICE_PRECISION, PRICE_SCALE), server_default="0", default=Decimal(0)
    )
    gateway_charge_percent: Mapped[Decimal] = mapped_column(
        Numeric(TAX_PERCENT_PRECISION, PRICE_SCALE), server_default="0", default=Decimal(0)
    )
    response_note: Mapped[str | None] = mapped_column(String(NOTE_LENGTH), default=None)
    responded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    responded_at: Mapped[datetime | None] = mapped_column(default=None)

    payment: Mapped["BookingPayment | None"] = relationship(lazy="selectin", viewonly=True)
