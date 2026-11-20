import enum
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import EarningMessages
from app.repositories.setting_repository import SettingRepository

PLATFORM_FEE_DIRECT_ORDER_SETTING_KEY = "platform_fee_direct_order_percent"
PLATFORM_FEE_DEAL_ORDER_SETTING_KEY = "platform_fee_deal_order_percent"
PLATFORM_FEE_BOOKING_SETTING_KEY = "platform_fee_booking_percent"
COMMISSION_DIRECT_ORDER_SETTING_KEY = "commission_direct_order_percent"
COMMISSION_DEAL_ORDER_SETTING_KEY = "commission_deal_order_percent"
COMMISSION_BOOKING_SETTING_KEY = "commission_booking_percent"
GATEWAY_CHARGE_SETTING_KEY = "gateway_charge_percent"
COMMISSION_SHARES_SETTING_KEY = "commission_shares"
PAYOUT_FREQUENCY_SETTING_KEY = "payout_frequency"
PERCENT_SETTING_KEYS = frozenset(
    {
        PLATFORM_FEE_DIRECT_ORDER_SETTING_KEY,
        PLATFORM_FEE_DEAL_ORDER_SETTING_KEY,
        PLATFORM_FEE_BOOKING_SETTING_KEY,
        COMMISSION_DIRECT_ORDER_SETTING_KEY,
        COMMISSION_DEAL_ORDER_SETTING_KEY,
        COMMISSION_BOOKING_SETTING_KEY,
        GATEWAY_CHARGE_SETTING_KEY,
    }
)
FINANCE_SETTING_KEYS = PERCENT_SETTING_KEYS | {
    COMMISSION_SHARES_SETTING_KEY,
    PAYOUT_FREQUENCY_SETTING_KEY,
}
DEFAULT_PERCENT = "0"
DEFAULT_COMMISSION_SHARES = json.dumps({"super_admin": "100", "native_admin": "0", "promoter": "0"})
MIN_PERCENT = Decimal(0)
MAX_PERCENT = Decimal(100)
PERCENT_STEP = Decimal("0.01")
MONEY_STEP = Decimal("0.01")
HUNDRED = Decimal(100)
SHARE_KEYS = ("super_admin", "native_admin", "promoter")


class FeeKind(enum.StrEnum):
    DIRECT_ORDER = "direct_order"
    DEAL_ORDER = "deal_order"
    BOOKING = "booking"


class PayoutFrequency(enum.StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


DEFAULT_PAYOUT_FREQUENCY = PayoutFrequency.WEEKLY
PLATFORM_FEE_KEY_BY_KIND = {
    FeeKind.DIRECT_ORDER: PLATFORM_FEE_DIRECT_ORDER_SETTING_KEY,
    FeeKind.DEAL_ORDER: PLATFORM_FEE_DEAL_ORDER_SETTING_KEY,
    FeeKind.BOOKING: PLATFORM_FEE_BOOKING_SETTING_KEY,
}
COMMISSION_KEY_BY_KIND = {
    FeeKind.DIRECT_ORDER: COMMISSION_DIRECT_ORDER_SETTING_KEY,
    FeeKind.DEAL_ORDER: COMMISSION_DEAL_ORDER_SETTING_KEY,
    FeeKind.BOOKING: COMMISSION_BOOKING_SETTING_KEY,
}


@dataclass(frozen=True)
class Charge:
    percent: Decimal
    amount: Decimal


@dataclass(frozen=True)
class CheckoutCharges:
    platform_fee: Charge
    commission: Charge
    gateway_charge_percent: Decimal


@dataclass(frozen=True)
class CommissionShares:
    super_admin: Decimal
    native_admin: Decimal
    promoter: Decimal


class ChargeTarget(Protocol):
    platform_fee_percent: Decimal
    platform_fee_amount: Decimal
    commission_percent: Decimal
    commission_amount: Decimal
    gateway_charge_percent: Decimal


def percent_of(base: Decimal, percent: Decimal) -> Decimal:
    return (base * percent / HUNDRED).quantize(MONEY_STEP, ROUND_HALF_UP)


def parse_percent(key: str, raw: object) -> Decimal:
    message = EarningMessages.FEE_PERCENT_INVALID.format(
        key=key, minimum=MIN_PERCENT, maximum=MAX_PERCENT
    )
    try:
        percent = Decimal(str(raw if raw is not None else "").strip())
    except InvalidOperation as exc:
        raise BusinessRuleError(message) from exc
    if not percent.is_finite() or percent != percent.quantize(PERCENT_STEP):
        raise BusinessRuleError(message)
    if not MIN_PERCENT <= percent <= MAX_PERCENT:
        raise BusinessRuleError(message)
    return percent.quantize(PERCENT_STEP)


def parse_commission_shares(raw: str | None) -> CommissionShares:
    try:
        data = json.loads(raw or "")
    except json.JSONDecodeError as exc:
        raise BusinessRuleError(EarningMessages.COMMISSION_SHARES_INVALID) from exc
    if not isinstance(data, dict) or set(data) != set(SHARE_KEYS):
        raise BusinessRuleError(EarningMessages.COMMISSION_SHARES_INVALID)
    shares = {
        key: parse_percent(f"{COMMISSION_SHARES_SETTING_KEY}.{key}", data[key])
        for key in SHARE_KEYS
    }
    total = sum(shares.values())
    if total != HUNDRED:
        raise BusinessRuleError(EarningMessages.COMMISSION_SHARES_TOTAL_INVALID.format(total=total))
    return CommissionShares(**shares)


def parse_payout_frequency(raw: str | None) -> PayoutFrequency:
    try:
        return PayoutFrequency((raw or "").strip())
    except ValueError as exc:
        raise BusinessRuleError(EarningMessages.PAYOUT_FREQUENCY_INVALID) from exc


def snapshot_charges(target: ChargeTarget, charges: CheckoutCharges) -> None:
    target.platform_fee_percent = charges.platform_fee.percent
    target.platform_fee_amount = charges.platform_fee.amount
    target.commission_percent = charges.commission.percent
    target.commission_amount = charges.commission.amount
    target.gateway_charge_percent = charges.gateway_charge_percent


class FinanceSettingsService:
    def __init__(self, db: Session) -> None:
        self._settings = SettingRepository(db)

    def ensure_valid(self, key: str, value: str | None) -> None:
        if key in PERCENT_SETTING_KEYS:
            parse_percent(key, value)
        elif key == COMMISSION_SHARES_SETTING_KEY:
            parse_commission_shares(value)
        elif key == PAYOUT_FREQUENCY_SETTING_KEY:
            parse_payout_frequency(value)

    def charges_for(self, kind: FeeKind, subtotal: Decimal) -> CheckoutCharges:
        platform_percent = self._percent(PLATFORM_FEE_KEY_BY_KIND[kind])
        commission_percent = self._percent(COMMISSION_KEY_BY_KIND[kind])
        return CheckoutCharges(
            platform_fee=Charge(platform_percent, percent_of(subtotal, platform_percent)),
            commission=Charge(commission_percent, percent_of(subtotal, commission_percent)),
            gateway_charge_percent=self._percent(GATEWAY_CHARGE_SETTING_KEY),
        )

    def commission_shares(self) -> CommissionShares:
        return parse_commission_shares(
            self._raw(COMMISSION_SHARES_SETTING_KEY, DEFAULT_COMMISSION_SHARES)
        )

    def payout_frequency(self) -> PayoutFrequency:
        return parse_payout_frequency(
            self._raw(PAYOUT_FREQUENCY_SETTING_KEY, DEFAULT_PAYOUT_FREQUENCY.value)
        )

    def _percent(self, key: str) -> Decimal:
        return parse_percent(key, self._raw(key, DEFAULT_PERCENT))

    def _raw(self, key: str, default: str) -> str:
        setting = self._settings.get_by_key(key)
        return setting.value if setting is not None and setting.value is not None else default
