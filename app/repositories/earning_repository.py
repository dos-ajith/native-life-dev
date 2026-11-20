from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.earning import (
    DuesStatus,
    Earning,
    EarningBeneficiary,
    EarningPaymentMode,
    EarningSource,
    EarningStatus,
)
from app.schemas.earning import EarningListQuery
from app.schemas.pagination import PaginationParams

ONE_DAY = timedelta(days=1)
MONEY_STEP = Decimal("0.01")
ALWAYS_PAYABLE_BENEFICIARIES = (
    EarningBeneficiary.NATIVE_ADMIN,
    EarningBeneficiary.PROMOTER_COMMISSION,
)


@dataclass(frozen=True)
class EarningTotals:
    beneficiary_type: EarningBeneficiary
    currency: str
    entry_count: int
    pending_amount: Decimal
    available_amount: Decimal
    settled_amount: Decimal
    reversed_amount: Decimal
    platform_fee_amount: Decimal
    commission_amount: Decimal
    gateway_charge_amount: Decimal
    dues_owed: Decimal


def query_filters(query: EarningListQuery) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if query.status is not None:
        filters.append(Earning.status == query.status)
    if query.source_type is not None:
        filters.append(Earning.source_type == query.source_type)
    if query.date_from is not None:
        filters.append(Earning.created_at >= datetime.combine(query.date_from, time.min))
    if query.date_to is not None:
        filters.append(Earning.created_at < datetime.combine(query.date_to + ONE_DAY, time.min))
    return filters


def _sum_where(
    condition: ColumnElement[bool], column: InstrumentedAttribute[Decimal]
) -> ColumnElement[Any]:
    return func.coalesce(func.sum(case((condition, column), else_=0)), 0)


def _money(value: Any) -> Decimal:
    return Decimal(value).quantize(MONEY_STEP)


class EarningRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def for_source(self, source_type: EarningSource, source_id: UUID) -> list[Earning]:
        column = Earning.order_id if source_type == EarningSource.ORDER else Earning.booking_id
        return list(self._db.scalars(select(Earning).where(column == source_id)).all())

    def add(self, earning: Earning) -> Earning:
        self._db.add(earning)
        return earning

    def delete(self, earning: Earning) -> None:
        self._db.delete(earning)

    def commit(self) -> None:
        self._db.commit()

    def page(
        self, filters: list[ColumnElement[bool]], params: PaginationParams
    ) -> tuple[list[Earning], int]:
        condition = and_(*filters) if filters else None
        count_query = select(func.count()).select_from(Earning)
        rows_query = select(Earning)
        if condition is not None:
            count_query = count_query.where(condition)
            rows_query = rows_query.where(condition)
        total = self._db.scalar(count_query) or 0
        rows = self._db.scalars(
            rows_query.order_by(Earning.created_at.desc(), Earning.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return list(rows), total

    def totals(self, filters: list[ColumnElement[bool]]) -> list[EarningTotals]:
        not_reversed = Earning.status != EarningStatus.REVERSED
        query = select(
            Earning.beneficiary_type,
            Earning.currency,
            func.count(),
            _sum_where(Earning.status == EarningStatus.PENDING, Earning.net_amount),
            _sum_where(Earning.status == EarningStatus.AVAILABLE, Earning.net_amount),
            _sum_where(Earning.status == EarningStatus.SETTLED, Earning.net_amount),
            _sum_where(Earning.status == EarningStatus.REVERSED, Earning.net_amount),
            _sum_where(not_reversed, Earning.platform_fee_amount),
            _sum_where(not_reversed, Earning.commission_amount),
            _sum_where(not_reversed, Earning.gateway_charge_amount),
            _sum_where(Earning.dues_status == DuesStatus.OWED, Earning.dues_amount),
        )
        if filters:
            query = query.where(and_(*filters))
        rows = self._db.execute(
            query.group_by(Earning.beneficiary_type, Earning.currency).order_by(
                Earning.beneficiary_type, Earning.currency
            )
        ).all()
        return [
            EarningTotals(
                beneficiary_type=row[0],
                currency=row[1],
                entry_count=row[2],
                pending_amount=_money(row[3]),
                available_amount=_money(row[4]),
                settled_amount=_money(row[5]),
                reversed_amount=_money(row[6]),
                platform_fee_amount=_money(row[7]),
                commission_amount=_money(row[8]),
                gateway_charge_amount=_money(row[9]),
                dues_owed=_money(row[10]),
            )
            for row in rows
        ]

    def payable(
        self, before: datetime, payee: ColumnElement[bool] | None = None, lock: bool = False
    ) -> list[Earning]:
        query = select(Earning).where(
            Earning.status == EarningStatus.AVAILABLE,
            Earning.payout_id.is_(None),
            Earning.available_at < before,
            Earning.beneficiary_type != EarningBeneficiary.PLATFORM,
            or_(
                Earning.payment_mode == EarningPaymentMode.ONLINE,
                Earning.beneficiary_type.in_(ALWAYS_PAYABLE_BENEFICIARIES),
            ),
        )
        return self._rows(query, payee, lock)

    def dues_owed(
        self, payee: ColumnElement[bool] | None = None, lock: bool = False, unlinked: bool = False
    ) -> list[Earning]:
        query = select(Earning).where(
            Earning.dues_status == DuesStatus.OWED, Earning.payout_id.is_(None)
        )
        if unlinked:
            query = query.where(Earning.dues_payment_id.is_(None))
        return self._rows(query, payee, lock)

    def for_payout(self, payout_id: UUID) -> list[Earning]:
        return list(
            self._db.scalars(
                select(Earning)
                .where(Earning.payout_id == payout_id)
                .order_by(Earning.created_at, Earning.id)
            ).all()
        )

    def for_dues_payment(self, dues_payment_id: UUID) -> list[Earning]:
        return list(
            self._db.scalars(
                select(Earning).where(Earning.dues_payment_id == dues_payment_id)
            ).all()
        )

    def _rows(
        self, query: Select[Earning], payee: ColumnElement[bool] | None, lock: bool
    ) -> list[Earning]:
        if payee is not None:
            query = query.where(payee)
        if lock:
            query = query.with_for_update()
        return list(self._db.scalars(query.order_by(Earning.created_at, Earning.id)).all())
