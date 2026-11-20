from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.booking import (
    CURRENCY_LENGTH,
    PRICE_PRECISION,
    PRICE_SCALE,
    TAX_PERCENT_PRECISION,
)
from app.models.payment_status import PaymentStatus, payment_status_column_type

PROVIDER_LENGTH = 20
PROVIDER_ID_LENGTH = 64
PAYMENT_URL_LENGTH = 500


class BookingPayment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "booking_payments"

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), unique=True
    )
    provider: Mapped[str] = mapped_column(String(PROVIDER_LENGTH))
    provider_link_id: Mapped[str] = mapped_column(String(PROVIDER_ID_LENGTH), unique=True)
    payment_url: Mapped[str] = mapped_column(String(PAYMENT_URL_LENGTH))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    party_size: Mapped[int]
    subtotal: Mapped[Decimal] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(TAX_PERCENT_PRECISION, PRICE_SCALE))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(PRICE_PRECISION, PRICE_SCALE))
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    status: Mapped[PaymentStatus] = mapped_column(
        payment_status_column_type(), default=PaymentStatus.PENDING
    )
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(PROVIDER_ID_LENGTH), default=None
    )
    expires_at: Mapped[datetime]
    paid_at: Mapped[datetime | None] = mapped_column(default=None)
