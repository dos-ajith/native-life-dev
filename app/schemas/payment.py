from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from app.models.booking_payment import BookingPayment
from app.models.dues_payment import DuesPayment
from app.models.order_payment import OrderPayment
from app.models.payment_status import PaymentStatus
from app.schemas.base import BaseReadSchema


class PaymentSubject(StrEnum):
    BOOKING = "booking"
    ORDER = "order"
    DUES = "dues"


class PaymentStatusRead(BaseReadSchema):
    subject: PaymentSubject
    subject_id: UUID
    status: PaymentStatus
    total_amount: Decimal
    currency: str
    paid_at: datetime | None

    @classmethod
    def from_booking_payment(cls, payment: BookingPayment) -> Self:
        return cls(
            subject=PaymentSubject.BOOKING,
            subject_id=payment.booking_id,
            status=payment.status,
            total_amount=payment.total_amount,
            currency=payment.currency,
            paid_at=payment.paid_at,
        )

    @classmethod
    def from_order_payment(cls, payment: OrderPayment) -> Self:
        return cls(
            subject=PaymentSubject.ORDER,
            subject_id=payment.order_id,
            status=payment.status,
            total_amount=payment.total_amount,
            currency=payment.currency,
            paid_at=payment.paid_at,
        )

    @classmethod
    def from_dues_payment(cls, payment: DuesPayment) -> Self:
        return cls(
            subject=PaymentSubject.DUES,
            subject_id=payment.id,
            status=payment.status,
            total_amount=payment.total_amount,
            currency=payment.currency,
            paid_at=payment.paid_at,
        )


class OrderPaymentRead(BaseReadSchema):
    id: UUID
    order_id: UUID
    provider: str
    status: PaymentStatus
    payment_url: str
    total_amount: Decimal
    currency: str
    expires_at: datetime
    paid_at: datetime | None
