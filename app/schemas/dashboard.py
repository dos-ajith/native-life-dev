from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import OrderStatus, PaymentMethod

MIN_TREND_MONTHS = 1
MAX_TREND_MONTHS = 24
DEFAULT_TREND_MONTHS = 12


class DashboardQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    months: int = Field(default=DEFAULT_TREND_MONTHS, ge=MIN_TREND_MONTHS, le=MAX_TREND_MONTHS)


class OrderStatusCountRead(BaseModel):
    status: OrderStatus
    count: int


class PaymentMethodSplitRead(BaseModel):
    payment_method: PaymentMethod
    order_count: int
    order_value: Decimal


class OrdersOverviewRead(BaseModel):
    currency: str
    total_orders: int
    by_status: list[OrderStatusCountRead]
    revenue_orders: int
    total_value: Decimal
    average_value: Decimal
    by_payment_method: list[PaymentMethodSplitRead]


class MonthlyTrendRead(BaseModel):
    month: str
    orders: int | None
    revenue: Decimal | None
    new_users: int | None
    new_businesses: int | None


class StatCardRead(BaseModel):
    total: int
    this_month: int
    last_month: int
    change_percent: float | None


class PendingApprovalsRead(BaseModel):
    total: int
    role_upgrade_requests: int
    business_verifications: int
    native_place_suggestions: int


class DashboardStatsRead(BaseModel):
    registered_users: StatCardRead | None
    active_businesses: StatCardRead | None
    native_places: StatCardRead | None
    pending_approvals: PendingApprovalsRead | None


class DashboardSummaryRead(BaseModel):
    months: int
    period_start: date
    period_end: date
    stats: DashboardStatsRead
    orders: OrdersOverviewRead | None
    trends: list[MonthlyTrendRead]
