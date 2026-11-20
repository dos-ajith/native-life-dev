from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.permissions import PermissionName
from app.core.timezone import naive_app_now
from app.models.order import OrderStatus, PaymentMethod
from app.models.user import User
from app.repositories.dashboard_repository import (
    MONEY_STEP,
    CreatedWindow,
    DashboardRepository,
    MonthlyOrderTotals,
    OrderGroupTotals,
    StatCounts,
)
from app.schemas.dashboard import (
    DashboardQuery,
    DashboardStatsRead,
    DashboardSummaryRead,
    MonthlyTrendRead,
    OrdersOverviewRead,
    OrderStatusCountRead,
    PaymentMethodSplitRead,
    PendingApprovalsRead,
    StatCardRead,
)
from app.services.authorization_service import has_permission

MONTHS_PER_YEAR = 12
MONTH_LABEL_FORMAT = "%Y-%m"
PERCENT = 100
PERCENT_DECIMALS = 1
ONE_DAY = timedelta(days=1)
ZERO = Decimal(0).quantize(MONEY_STEP)
NO_MONTHLY_ORDERS = MonthlyOrderTotals(placed_orders=0, revenue=ZERO)


def month_starts(today: date, months: int) -> list[date]:
    current = today.year * MONTHS_PER_YEAR + today.month - 1
    return [
        date(index // MONTHS_PER_YEAR, index % MONTHS_PER_YEAR + 1, 1)
        for index in range(current - months + 1, current + 1)
    ]


def average(total: Decimal, count: int) -> Decimal:
    return (total / count).quantize(MONEY_STEP) if count else ZERO


def change_percent(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * PERCENT, PERCENT_DECIMALS)


def month_windows(today: date) -> tuple[CreatedWindow, CreatedWindow]:
    last_month, this_month = (datetime.combine(day, time.min) for day in month_starts(today, 2))
    tomorrow = datetime.combine(today + ONE_DAY, time.min)
    return CreatedWindow(this_month, tomorrow), CreatedWindow(last_month, this_month)


def stat_card(counts: StatCounts) -> StatCardRead:
    return StatCardRead(
        total=counts.total,
        this_month=counts.this_month,
        last_month=counts.last_month,
        change_percent=change_percent(counts.this_month, counts.last_month),
    )


def build_orders_overview(groups: Iterable[OrderGroupTotals], currency: str) -> OrdersOverviewRead:
    status_counts: Counter[OrderStatus] = Counter()
    revenue_counts: Counter[PaymentMethod] = Counter()
    revenue_values = dict.fromkeys(PaymentMethod, ZERO)
    for group in groups:
        status_counts[group.status] += group.order_count
        revenue_counts[group.payment_method] += group.revenue_count
        revenue_values[group.payment_method] += group.revenue
    splits = [
        PaymentMethodSplitRead(
            payment_method=method,
            order_count=revenue_counts[method],
            order_value=revenue_values[method],
        )
        for method in PaymentMethod
    ]
    revenue_orders = sum(revenue_counts.values())
    total_value = sum(revenue_values.values(), ZERO)
    return OrdersOverviewRead(
        currency=currency,
        total_orders=sum(status_counts.values()),
        by_status=[
            OrderStatusCountRead(status=status, count=status_counts[status])
            for status in OrderStatus
        ],
        revenue_orders=revenue_orders,
        total_value=total_value,
        average_value=average(total_value, revenue_orders),
        by_payment_method=splits,
    )


@dataclass(frozen=True)
class DashboardAccess:
    users: bool
    businesses: bool
    native_places: bool
    approvals: bool
    orders: bool

    @classmethod
    def for_user(cls, user: User) -> "DashboardAccess":
        return cls(
            users=has_permission(user, PermissionName.DASHBOARD_VIEW_USERS),
            businesses=has_permission(user, PermissionName.DASHBOARD_VIEW_BUSINESSES),
            native_places=has_permission(user, PermissionName.DASHBOARD_VIEW_NATIVE_PLACES),
            approvals=has_permission(user, PermissionName.DASHBOARD_VIEW_APPROVALS),
            orders=has_permission(user, PermissionName.DASHBOARD_VIEW_ORDERS),
        )


def _visible[K, V](allowed: bool, fetch: Callable[[], Mapping[K, V]]) -> Mapping[K, V] | None:
    return fetch() if allowed else None


def _value_for[K, V](values: Mapping[K, V] | None, key: K, default: V) -> V | None:
    return None if values is None else values.get(key, default)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._dashboard = DashboardRepository(db)

    def summary(
        self, query: DashboardQuery, currency: str, access: DashboardAccess
    ) -> DashboardSummaryRead:
        today = naive_app_now().date()
        months = month_starts(today, query.months)
        since = datetime.combine(months[0], time.min)
        return DashboardSummaryRead(
            months=query.months,
            period_start=months[0],
            period_end=today,
            stats=self._stats(today, access),
            orders=self._orders_overview(since, currency) if access.orders else None,
            trends=self._trends(months, since, currency, access),
        )

    def _stats(self, today: date, access: DashboardAccess) -> DashboardStatsRead:
        dashboard = self._dashboard
        this_window, last_window = month_windows(today)
        return DashboardStatsRead(
            registered_users=stat_card(dashboard.user_stats(this_window, last_window))
            if access.users
            else None,
            active_businesses=stat_card(dashboard.active_business_stats(this_window, last_window))
            if access.businesses
            else None,
            native_places=stat_card(dashboard.native_place_stats(this_window, last_window))
            if access.native_places
            else None,
            pending_approvals=self._pending_approvals() if access.approvals else None,
        )

    def _pending_approvals(self) -> PendingApprovalsRead:
        counts = self._dashboard.pending_approval_counts()
        return PendingApprovalsRead(
            total=counts.role_upgrade_requests
            + counts.business_verifications
            + counts.native_place_suggestions,
            role_upgrade_requests=counts.role_upgrade_requests,
            business_verifications=counts.business_verifications,
            native_place_suggestions=counts.native_place_suggestions,
        )

    def _orders_overview(self, since: datetime, currency: str) -> OrdersOverviewRead:
        groups = self._dashboard.order_totals_by_status_and_method(since, currency)
        return build_orders_overview(groups, currency)

    def _trends(
        self, months: list[date], since: datetime, currency: str, access: DashboardAccess
    ) -> list[MonthlyTrendRead]:
        dashboard = self._dashboard
        orders = _visible(access.orders, lambda: dashboard.monthly_order_totals(since, currency))
        users = _visible(access.users, lambda: dashboard.monthly_new_users(since))
        businesses = _visible(access.businesses, lambda: dashboard.monthly_new_businesses(since))
        trends = []
        for month in months:
            order_totals = _value_for(orders, month, NO_MONTHLY_ORDERS)
            trends.append(
                MonthlyTrendRead(
                    month=month.strftime(MONTH_LABEL_FORMAT),
                    orders=order_totals.placed_orders if order_totals else None,
                    revenue=order_totals.revenue if order_totals else None,
                    new_users=_value_for(users, month, 0),
                    new_businesses=_value_for(businesses, month, 0),
                )
            )
        return trends
