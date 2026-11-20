from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.booking_payment import PAYMENT_URL_LENGTH, PROVIDER_ID_LENGTH, PROVIDER_LENGTH
from app.models.order import CURRENCY_LENGTH, LINE_TOTAL_PRECISION, PRICE_SCALE
from app.models.payment_status import PaymentStatus, payment_status_column_type


class DuesPayment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dues_payments"
    __table_args__ = (
        Index("ix_dues_payments_user_id", "user_id"),
        Index("ix_dues_payments_business_id", "business_id"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    business_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="SET NULL"), default=None
    )
    provider: Mapped[str] = mapped_column(String(PROVIDER_LENGTH))
    provider_link_id: Mapped[str] = mapped_column(String(PROVIDER_ID_LENGTH), unique=True)
    payment_url: Mapped[str] = mapped_column(String(PAYMENT_URL_LENGTH))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(LINE_TOTAL_PRECISION, PRICE_SCALE))
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    status: Mapped[PaymentStatus] = mapped_column(
        payment_status_column_type(), default=PaymentStatus.PENDING
    )
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(PROVIDER_ID_LENGTH), default=None
    )
    expires_at: Mapped[datetime]
    paid_at: Mapped[datetime | None] = mapped_column(default=None)
