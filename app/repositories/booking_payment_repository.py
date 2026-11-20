from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.booking_payment import BookingPayment
from app.models.payment_status import PaymentStatus

REFRESH = {"populate_existing": True}


class BookingPaymentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, payment: BookingPayment) -> BookingPayment:
        self._db.add(payment)
        self._db.flush()
        return payment

    def get_by_link_id(self, provider_link_id: str) -> BookingPayment | None:
        return self._db.scalar(
            select(BookingPayment)
            .where(BookingPayment.provider_link_id == provider_link_id)
            .execution_options(**REFRESH)
        )

    def settle_pending(
        self,
        payment_id: UUID,
        target: PaymentStatus,
        provider_payment_id: str | None,
        paid_at: datetime | None,
    ) -> bool:
        result = self._db.execute(
            update(BookingPayment)
            .where(
                BookingPayment.id == payment_id,
                BookingPayment.status == PaymentStatus.PENDING,
            )
            .values(status=target, provider_payment_id=provider_payment_id, paid_at=paid_at)
        )
        return result.rowcount == 1  # type: ignore[attr-defined, no-any-return]
