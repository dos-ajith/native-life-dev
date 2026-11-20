from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, ScalarSelect, Select, and_, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.business import Business, BusinessStatus, BusinessVerificationStatus
from app.models.native_place_suggestion import NativePlaceSuggestion, NativePlaceSuggestionStatus
from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.models.user import User
from app.models.user_native_place import UserNativePlace

MONTH = "month"
MONEY_STEP = Decimal("0.01")
NOT_PLACED_STATUSES = (OrderStatus.AWAITING_PAYMENT,)
NON_REVENUE_STATUSES = (OrderStatus.AWAITING_PAYMENT, OrderStatus.CANCELLED)

type DateColumn = ColumnElement[datetime] | InstrumentedAttribute[datetime]


@dataclass(frozen=True)
class CreatedWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class StatCounts:
    total: int
    this_month: int
    last_month: int


@dataclass(frozen=True)
class PendingApprovalCounts:
    role_upgrade_requests: int
    business_verifications: int
    native_place_suggestions: int


@dataclass(frozen=True)
class OrderGroupTotals:
    status: OrderStatus
    payment_method: PaymentMethod
    order_count: int
    revenue_count: int
    revenue: Decimal


@dataclass(frozen=True)
class MonthlyOrderTotals:
    placed_orders: int
    revenue: Decimal


def _money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(MONEY_STEP)


def _month_bucket(column: DateColumn) -> ColumnElement[Any]:
    return func.date_trunc(MONTH, column)


def _in_window(column: DateColumn, window: CreatedWindow) -> ColumnElement[bool]:
    return and_(column >= window.start, column < window.end)


def _counts_by_window(
    column: DateColumn, this_window: CreatedWindow, last_window: CreatedWindow
) -> tuple[ColumnElement[int], ColumnElement[int], ColumnElement[int]]:
    return (
        func.count(),
        func.count().filter(_in_window(column, this_window)),
        func.count().filter(_in_window(column, last_window)),
    )


def _is_revenue(currency: str) -> ColumnElement[bool]:
    return and_(Order.status.not_in(NON_REVENUE_STATUSES), Order.currency == currency)


def _count_where(model: type[Any], *conditions: ColumnElement[bool]) -> ScalarSelect[int]:
    return select(func.count()).select_from(model).where(*conditions).scalar_subquery()


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def user_stats(self, this_window: CreatedWindow, last_window: CreatedWindow) -> StatCounts:
        return self._stat_counts(
            select(*_counts_by_window(User.created_at, this_window, last_window))
            .select_from(User)
            .where(User.deleted_at.is_(None))
        )

    def active_business_stats(
        self, this_window: CreatedWindow, last_window: CreatedWindow
    ) -> StatCounts:
        return self._stat_counts(
            select(*_counts_by_window(Business.created_at, this_window, last_window))
            .select_from(Business)
            .where(Business.deleted_at.is_(None), Business.status == BusinessStatus.ACTIVE)
        )

    def native_place_stats(
        self, this_window: CreatedWindow, last_window: CreatedWindow
    ) -> StatCounts:
        places = (
            select(func.min(UserNativePlace.created_at).label("first_chosen"))
            .join(User, User.id == UserNativePlace.user_id)
            .where(User.deleted_at.is_(None))
            .group_by(UserNativePlace.village_id)
            .subquery()
        )
        return self._stat_counts(
            select(*_counts_by_window(places.c.first_chosen, this_window, last_window)).select_from(
                places
            )
        )

    def pending_approval_counts(self) -> PendingApprovalCounts:
        role_upgrades, businesses, suggestions = self._db.execute(
            select(
                _count_where(
                    RoleUpgradeRequest,
                    RoleUpgradeRequest.status == RoleUpgradeRequestStatus.PENDING,
                ),
                _count_where(
                    Business,
                    Business.deleted_at.is_(None),
                    Business.verification_status == BusinessVerificationStatus.PENDING,
                ),
                _count_where(
                    NativePlaceSuggestion,
                    NativePlaceSuggestion.status == NativePlaceSuggestionStatus.PENDING,
                ),
            )
        ).one()
        return PendingApprovalCounts(
            role_upgrade_requests=role_upgrades,
            business_verifications=businesses,
            native_place_suggestions=suggestions,
        )

    def order_totals_by_status_and_method(
        self, since: datetime, currency: str
    ) -> list[OrderGroupTotals]:
        is_revenue = _is_revenue(currency)
        rows = self._db.execute(
            select(
                Order.status,
                Order.payment_method,
                func.count(),
                func.count().filter(is_revenue),
                func.sum(Order.total_amount).filter(is_revenue),
            )
            .where(Order.created_at >= since)
            .group_by(Order.status, Order.payment_method)
        ).all()
        return [
            OrderGroupTotals(
                status=status,
                payment_method=method,
                order_count=count,
                revenue_count=revenue_count,
                revenue=_money(revenue),
            )
            for status, method, count, revenue_count, revenue in rows
        ]

    def monthly_order_totals(
        self, since: datetime, currency: str
    ) -> dict[date, MonthlyOrderTotals]:
        bucket = _month_bucket(Order.created_at)
        rows = self._db.execute(
            select(
                bucket,
                func.count().filter(Order.status.not_in(NOT_PLACED_STATUSES)),
                func.sum(Order.total_amount).filter(_is_revenue(currency)),
            )
            .where(Order.created_at >= since)
            .group_by(bucket)
        ).all()
        return {
            month.date(): MonthlyOrderTotals(placed_orders=placed, revenue=_money(revenue))
            for month, placed, revenue in rows
        }

    def monthly_new_users(self, since: datetime) -> dict[date, int]:
        return self._monthly_counts(User.created_at, since)

    def monthly_new_businesses(self, since: datetime) -> dict[date, int]:
        return self._monthly_counts(Business.created_at, since)

    def _stat_counts(self, statement: Select[int, int, int]) -> StatCounts:
        total, this_month, last_month = self._db.execute(statement).one()
        return StatCounts(total=total, this_month=this_month, last_month=last_month)

    def _monthly_counts(self, column: DateColumn, since: datetime) -> dict[date, int]:
        bucket = _month_bucket(column)
        rows = self._db.execute(
            select(bucket, func.count()).where(column >= since).group_by(bucket)
        ).all()
        return {month.date(): count for month, count in rows}
