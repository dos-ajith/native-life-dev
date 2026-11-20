import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Numeric, Sequence, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

AMOUNT_PRECISION = 14
AMOUNT_SCALE = 2
CURRENCY_LENGTH = 3
PAYOUT_NUMBER_LENGTH = 20
REFERENCE_LENGTH = 100
PROVIDER_ID_LENGTH = 100
NOTE_LENGTH = 500

PAYOUT_NUMBER_SEQUENCE = Sequence("payout_number_seq", start=1001, metadata=Base.metadata)


class PayeeType(enum.StrEnum):
    BUSINESS = "business"
    INDIVIDUAL_SELLER = "individual_seller"
    PROMOTER = "promoter"
    NATIVE_ADMIN = "native_admin"


class PayoutStatus(enum.StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PayoutMethod(enum.StrEnum):
    MANUAL = "manual"
    RAZORPAYX = "razorpayx"


def _enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Payout(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payouts"
    __table_args__ = (
        Index("ix_payouts_user_id", "user_id"),
        Index("ix_payouts_business_id", "business_id"),
    )

    payout_number: Mapped[str] = mapped_column(String(PAYOUT_NUMBER_LENGTH), unique=True)
    payee_type: Mapped[PayeeType] = mapped_column(_enum(PayeeType, "payee_type"))
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    business_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="SET NULL"), default=None
    )
    period_end: Mapped[date]
    earnings_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    dues_offset_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    payout_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    status: Mapped[PayoutStatus] = mapped_column(
        _enum(PayoutStatus, "payout_status"), default=PayoutStatus.DRAFT
    )
    method: Mapped[PayoutMethod | None] = mapped_column(
        _enum(PayoutMethod, "payout_method"), default=None
    )
    payment_reference: Mapped[str | None] = mapped_column(String(REFERENCE_LENGTH), default=None)
    provider_payout_id: Mapped[str | None] = mapped_column(
        String(PROVIDER_ID_LENGTH), unique=True, default=None
    )
    failure_reason: Mapped[str | None] = mapped_column(Text(), default=None)
    note: Mapped[str | None] = mapped_column(String(NOTE_LENGTH), default=None)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    paid_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    paid_at: Mapped[datetime | None] = mapped_column(default=None)
