from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus
from app.models.order_payment import OrderPayment
from app.models.payment_status import PaymentStatus

REFRESH = {"populate_existing": True}


class OrderPaymentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, payment: OrderPayment) -> OrderPayment:
        self._db.add(payment)
        self._db.flush()
        return payment

    def get_by_link_id(self, provider_link_id: str) -> OrderPayment | None:
        return self._db.scalar(
            select(OrderPayment)
            .where(OrderPayment.provider_link_id == provider_link_id)
            .execution_options(**REFRESH)
        )

    def list_overdue_holds(self, now: datetime) -> list[OrderPayment]:
        return list(
            self._db.scalars(
                select(OrderPayment)
                .join(Order, Order.id == OrderPayment.order_id)
                .where(
                    Order.status == OrderStatus.AWAITING_PAYMENT,
                    OrderPayment.status == PaymentStatus.PENDING,
                    OrderPayment.expires_at < now,
                )
            )
        )

    def settle_pending(
        self,
        payment_id: UUID,
        target: PaymentStatus,
        provider_payment_id: str | None,
        paid_at: datetime | None,
    ) -> bool:
        result = self._db.execute(
            update(OrderPayment)
            .where(
                OrderPayment.id == payment_id,
                OrderPayment.status == PaymentStatus.PENDING,
            )
            .values(status=target, provider_payment_id=provider_payment_id, paid_at=paid_at)
        )
        return result.rowcount == 1  # type: ignore[attr-defined, no-any-return]
