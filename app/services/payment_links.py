from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import get_settings
from app.core.timezone import app_now
from app.models.payment_status import PaymentStatus

MINOR_UNITS_PER_MAJOR = 100
GATEWAY_STATUS_TARGETS = {
    "paid": PaymentStatus.PAID,
    "expired": PaymentStatus.EXPIRED,
    "cancelled": PaymentStatus.CANCELLED,
}


def minor_units(amount: Decimal) -> int:
    return int((amount * MINOR_UNITS_PER_MAJOR).to_integral_value(ROUND_HALF_UP))


def link_expires_at(minutes: int | None = None) -> datetime:
    window = get_settings().payment_link_expire_minutes if minutes is None else minutes
    return app_now() + timedelta(minutes=window)


def settled_status(gateway_status: str) -> PaymentStatus | None:
    return GATEWAY_STATUS_TARGETS.get(gateway_status)
