from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.orm import Session

from app.models.dues_payment import DuesPayment
from app.models.payment_status import PaymentStatus
from app.models.payout import PAYOUT_NUMBER_SEQUENCE, Payout
from app.models.payout_account import PayoutAccount
from app.schemas.pagination import PaginationParams

PAYOUT_NUMBER_PREFIX = "PO"


class PayoutRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def next_number(self) -> str:
        return (
            f"{PAYOUT_NUMBER_PREFIX}{self._db.scalar(select(PAYOUT_NUMBER_SEQUENCE.next_value()))}"
        )

    def add(self, payout: Payout) -> Payout:
        self._db.add(payout)
        self._db.flush()
        return payout

    def get(self, payout_id: UUID, lock: bool = False) -> Payout | None:
        query = select(Payout).where(Payout.id == payout_id)
        if lock:
            query = query.with_for_update()
        return self._db.scalar(query.execution_options(populate_existing=True))

    def get_by_provider_id(self, provider_payout_id: str) -> Payout | None:
        return self._db.scalar(
            select(Payout).where(Payout.provider_payout_id == provider_payout_id).with_for_update()
        )

    def page(
        self, filters: list[ColumnElement[bool]], params: PaginationParams
    ) -> tuple[list[Payout], int]:
        condition = and_(*filters) if filters else None
        count_query = select(func.count()).select_from(Payout)
        rows_query = select(Payout)
        if condition is not None:
            count_query = count_query.where(condition)
            rows_query = rows_query.where(condition)
        total = self._db.scalar(count_query) or 0
        rows = self._db.scalars(
            rows_query.order_by(Payout.created_at.desc(), Payout.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return list(rows), total

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()


class PayoutAccountRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def personal(self, user_id: UUID) -> PayoutAccount | None:
        return self._db.scalar(
            select(PayoutAccount).where(
                PayoutAccount.user_id == user_id, PayoutAccount.business_id.is_(None)
            )
        )

    def for_business(self, business_id: UUID) -> PayoutAccount | None:
        return self._db.scalar(
            select(PayoutAccount).where(PayoutAccount.business_id == business_id)
        )

    def add(self, account: PayoutAccount) -> PayoutAccount:
        self._db.add(account)
        return account

    def commit(self) -> None:
        self._db.commit()

    def refresh(self, account: PayoutAccount) -> None:
        self._db.refresh(account)


class DuesPaymentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, payment: DuesPayment) -> DuesPayment:
        self._db.add(payment)
        self._db.flush()
        return payment

    def get_by_link_id(self, link_id: str) -> DuesPayment | None:
        return self._db.scalar(
            select(DuesPayment)
            .where(DuesPayment.provider_link_id == link_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def pending_for(self, owner: ColumnElement[bool]) -> DuesPayment | None:
        return self._db.scalar(
            select(DuesPayment)
            .where(owner, DuesPayment.status == PaymentStatus.PENDING)
            .order_by(DuesPayment.created_at.desc())
        )

    def page(self, params: PaginationParams) -> tuple[list[DuesPayment], int]:
        total = self._db.scalar(select(func.count()).select_from(DuesPayment)) or 0
        rows = self._db.scalars(
            select(DuesPayment)
            .order_by(DuesPayment.created_at.desc(), DuesPayment.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return list(rows), total

    def settle_pending(
        self,
        payment: DuesPayment,
        status: PaymentStatus,
        provider_payment_id: str | None,
        paid_at: datetime | None,
    ) -> bool:
        if payment.status != PaymentStatus.PENDING:
            return False
        payment.status = status
        payment.provider_payment_id = provider_payment_id
        payment.paid_at = paid_at
        return True

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
