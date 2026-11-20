import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

AMOUNT_PRECISION = 14
AMOUNT_SCALE = 2
CURRENCY_LENGTH = 3
REFERENCE_NUMBER_LENGTH = 40


class EarningBeneficiary(enum.StrEnum):
    BUSINESS = "business"
    INDIVIDUAL_SELLER = "individual_seller"
    PROMOTER = "promoter"
    PROMOTER_COMMISSION = "promoter_commission"
    NATIVE_ADMIN = "native_admin"
    PLATFORM = "platform"


class EarningSource(enum.StrEnum):
    ORDER = "order"
    BOOKING = "booking"


class EarningPaymentMode(enum.StrEnum):
    ONLINE = "online"
    CASH = "cash"


class EarningStatus(enum.StrEnum):
    PENDING = "pending"
    AVAILABLE = "available"
    SETTLED = "settled"
    REVERSED = "reversed"


class DuesStatus(enum.StrEnum):
    OWED = "owed"
    PAID = "paid"
    OFFSET = "offset"


def _enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Earning(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "earnings"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(order_id, booking_id) = 1", name="ck_earnings_exactly_one_source"
        ),
        UniqueConstraint("order_id", "beneficiary_type", name="uq_earnings_order_beneficiary"),
        UniqueConstraint("booking_id", "beneficiary_type", name="uq_earnings_booking_beneficiary"),
        Index("ix_earnings_user_id", "user_id"),
        Index("ix_earnings_business_id", "business_id"),
        Index("ix_earnings_payout_id", "payout_id"),
    )

    beneficiary_type: Mapped[EarningBeneficiary] = mapped_column(
        _enum(EarningBeneficiary, "earning_beneficiary")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    business_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="SET NULL"), default=None
    )
    source_type: Mapped[EarningSource] = mapped_column(_enum(EarningSource, "earning_source"))
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), default=None
    )
    booking_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), default=None
    )
    reference_number: Mapped[str] = mapped_column(String(REFERENCE_NUMBER_LENGTH))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    platform_fee_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), server_default="0", default=Decimal(0)
    )
    gateway_charge_amount: Mapped[Decimal] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), server_default="0", default=Decimal(0)
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    dues_amount: Mapped[Decimal] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), server_default="0", default=Decimal(0)
    )
    dues_status: Mapped[DuesStatus | None] = mapped_column(
        _enum(DuesStatus, "earning_dues_status"), default=None
    )
    payout_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payouts.id", ondelete="SET NULL"), default=None
    )
    dues_payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dues_payments.id", ondelete="SET NULL"), default=None
    )
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    payment_mode: Mapped[EarningPaymentMode] = mapped_column(
        _enum(EarningPaymentMode, "earning_payment_mode")
    )
    status: Mapped[EarningStatus] = mapped_column(_enum(EarningStatus, "earning_status"))
    available_at: Mapped[datetime | None] = mapped_column(default=None)
    reversed_at: Mapped[datetime | None] = mapped_column(default=None)
    settled_at: Mapped[datetime | None] = mapped_column(default=None)
