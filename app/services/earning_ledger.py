from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.timezone import app_now, to_naive_app_time
from app.models.booking import Booking, BookingStatus
from app.models.business import Business
from app.models.earning import (
    DuesStatus,
    Earning,
    EarningBeneficiary,
    EarningPaymentMode,
    EarningSource,
    EarningStatus,
)
from app.models.notification import NotificationType
from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.payment_status import PaymentStatus
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.earning_repository import EarningRepository
from app.repositories.order_repository import OrderRepository
from app.services.activity_log_service import ActivityLogService
from app.services.booking_charges import booking_charges
from app.services.finance_settings_service import (
    CommissionShares,
    FinanceSettingsService,
    percent_of,
)
from app.services.notification_service import NotificationService

ZERO = Decimal(0)
CLOSED_BOOKING_STATUSES = frozenset({BookingStatus.CANCELLED, BookingStatus.REJECTED})
SELLER_BENEFICIARIES = frozenset(
    {EarningBeneficiary.BUSINESS, EarningBeneficiary.INDIVIDUAL_SELLER}
)
LOCKED_DUES_STATUSES = frozenset({DuesStatus.PAID, DuesStatus.OFFSET})


@dataclass(frozen=True)
class EntryPlan:
    beneficiary_type: EarningBeneficiary
    user_id: UUID | None
    business_id: UUID | None
    gross_amount: Decimal
    net_amount: Decimal
    platform_fee_amount: Decimal = ZERO
    commission_amount: Decimal = ZERO
    gateway_charge_amount: Decimal = ZERO
    dues_amount: Decimal = ZERO


@dataclass(frozen=True)
class SourcePlan:
    source_type: EarningSource
    source_id: UUID
    reference_number: str
    currency: str
    payment_mode: EarningPaymentMode
    status: EarningStatus | None
    entries: tuple[EntryPlan, ...]


@dataclass
class SyncResult:
    changed: bool = False
    dues_now_owed: list[Earning] = field(default_factory=list)


@dataclass(frozen=True)
class SaleAmounts:
    subtotal: Decimal
    tax: Decimal
    platform_fee: Decimal
    commission: Decimal
    gateway_charge: Decimal
    cash: bool


def order_status_for_earnings(order: Order) -> EarningStatus | None:
    if order.status == OrderStatus.AWAITING_PAYMENT:
        return None
    if order.status == OrderStatus.CANCELLED:
        return EarningStatus.REVERSED
    paid = order.payment_method == PaymentMethod.CASH_ON_DELIVERY or (
        order.payment is not None and order.payment.status == PaymentStatus.PAID
    )
    if not paid:
        return None
    if order.status == OrderStatus.DELIVERED:
        return EarningStatus.AVAILABLE
    return EarningStatus.PENDING


def booking_status_for_earnings(booking: Booking) -> EarningStatus | None:
    if booking.status in CLOSED_BOOKING_STATUSES:
        return EarningStatus.REVERSED
    if booking.status == BookingStatus.COMPLETED:
        return EarningStatus.AVAILABLE
    if _paid_online(booking):
        return EarningStatus.PENDING
    return None


def _paid_online(booking: Booking) -> bool:
    return booking.payment is not None and booking.payment.status == PaymentStatus.PAID


def split_entries(
    sale: SaleAmounts,
    seller: EntryPlan,
    shares: CommissionShares,
    native_admin_id: UUID | None,
    promoter_id: UUID | None,
) -> list[EntryPlan]:
    native_share = percent_of(sale.commission, shares.native_admin) if native_admin_id else ZERO
    promoter_share = percent_of(sale.commission, shares.promoter) if promoter_id else ZERO
    platform_total = sale.platform_fee + sale.commission - native_share - promoter_share
    platform_total += sale.gateway_charge
    entries = [seller]
    if native_share > ZERO:
        entries.append(
            EntryPlan(
                EarningBeneficiary.NATIVE_ADMIN,
                native_admin_id,
                seller.business_id,
                native_share,
                native_share,
            )
        )
    if promoter_share > ZERO:
        entries.append(
            EntryPlan(
                EarningBeneficiary.PROMOTER_COMMISSION,
                promoter_id,
                None,
                promoter_share,
                promoter_share,
            )
        )
    if platform_total > ZERO:
        entries.append(
            EntryPlan(
                EarningBeneficiary.PLATFORM,
                None,
                seller.business_id,
                platform_total,
                platform_total,
            )
        )
    return entries


def seller_entry(
    beneficiary: EarningBeneficiary,
    user_id: UUID | None,
    business_id: UUID | None,
    sale: SaleAmounts,
) -> EntryPlan:
    gross = sale.subtotal + sale.tax
    deductions = sale.platform_fee + sale.commission + sale.gateway_charge
    return EntryPlan(
        beneficiary,
        user_id,
        business_id,
        gross,
        gross - deductions,
        platform_fee_amount=sale.platform_fee,
        commission_amount=sale.commission,
        gateway_charge_amount=sale.gateway_charge,
        dues_amount=sale.platform_fee + sale.commission if sale.cash else ZERO,
    )


def _is_locked(row: Earning) -> bool:
    return (
        row.payout_id is not None
        or row.status == EarningStatus.SETTLED
        or row.dues_status in LOCKED_DUES_STATUSES
    )


class EarningLedger:
    def __init__(self, db: Session) -> None:
        self._earnings = EarningRepository(db)
        self._orders = OrderRepository(db)
        self._bookings = BookingRepository(db)
        self._deals = DealRepository(db)
        self._businesses = BusinessRepository(db)
        self._finance = FinanceSettingsService(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def sync_order(self, order_id: UUID, actor: User | None) -> None:
        order = self._orders.get(order_id)
        if order is not None:
            self._apply(self._order_plan(order), actor)

    def sync_booking(self, booking_id: UUID, actor: User | None) -> None:
        booking = self._bookings.get(booking_id)
        if booking is not None:
            self._apply(self._booking_plan(booking), actor)

    def _order_plan(self, order: Order) -> SourcePlan:
        online = order.payment_method == PaymentMethod.ONLINE
        sale = SaleAmounts(
            subtotal=sum((item.line_total for item in order.items), ZERO),
            tax=order.tax_amount,
            platform_fee=order.platform_fee_amount,
            commission=order.commission_amount,
            gateway_charge=(
                percent_of(order.total_amount, order.gateway_charge_percent) if online else ZERO
            ),
            cash=not online,
        )
        business = self._businesses.get_by_id(order.business_id) if order.business_id else None
        if business is not None:
            seller = seller_entry(EarningBeneficiary.BUSINESS, business.owner_id, business.id, sale)
        else:
            deal = self._deals.get_by_id(order.deal_id) if order.deal_id is not None else None
            seller = seller_entry(
                EarningBeneficiary.INDIVIDUAL_SELLER,
                deal.created_by if deal is not None else None,
                None,
                sale,
            )
        entries = split_entries(
            sale,
            seller,
            self._finance.commission_shares(),
            _native_admin_of(business),
            order.promoter_id,
        )
        if order.promoter_id is not None and order.delivery_fee > ZERO:
            entries.append(
                EntryPlan(
                    EarningBeneficiary.PROMOTER,
                    order.promoter_id,
                    None,
                    order.delivery_fee,
                    order.delivery_fee,
                )
            )
        return SourcePlan(
            source_type=EarningSource.ORDER,
            source_id=order.id,
            reference_number=order.order_number,
            currency=order.currency,
            payment_mode=EarningPaymentMode.ONLINE if online else EarningPaymentMode.CASH,
            status=order_status_for_earnings(order),
            entries=tuple(entries),
        )

    def _booking_plan(self, booking: Booking) -> SourcePlan:
        charges = booking_charges(booking)
        online = _paid_online(booking)
        paid_total = booking.payment.total_amount if booking.payment is not None else ZERO
        sale = SaleAmounts(
            subtotal=charges.subtotal,
            tax=charges.tax_amount,
            platform_fee=booking.platform_fee_amount,
            commission=booking.commission_amount,
            gateway_charge=(
                percent_of(paid_total, booking.gateway_charge_percent) if online else ZERO
            ),
            cash=not online,
        )
        business = self._businesses.get_by_id(booking.business_id)
        seller = seller_entry(
            EarningBeneficiary.BUSINESS,
            business.owner_id if business is not None else None,
            booking.business_id,
            sale,
        )
        entries = split_entries(
            sale, seller, self._finance.commission_shares(), _native_admin_of(business), None
        )
        return SourcePlan(
            source_type=EarningSource.BOOKING,
            source_id=booking.id,
            reference_number=booking.booking_number,
            currency=booking.currency,
            payment_mode=EarningPaymentMode.ONLINE if online else EarningPaymentMode.CASH,
            status=booking_status_for_earnings(booking),
            entries=tuple(entries),
        )

    def _apply(self, plan: SourcePlan, actor: User | None) -> None:
        existing = {
            row.beneficiary_type: row
            for row in self._earnings.for_source(plan.source_type, plan.source_id)
        }
        status = plan.status
        if status is None or (status == EarningStatus.REVERSED and not existing):
            return
        now = to_naive_app_time(app_now())
        result = SyncResult(changed=self._remove_stale(plan, existing, now))
        for entry in plan.entries:
            row = existing.get(entry.beneficiary_type)
            if status == EarningStatus.REVERSED and row is None:
                continue
            if row is None:
                row = self._earnings.add(self._new_row(plan, entry))
                result.changed = True
            _update_row(row, plan, entry, now, result)
        if not result.changed:
            return
        self._earnings.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EARNINGS_SYNCED,
            entity_type=plan.source_type.value,
            entity_id=plan.source_id,
            metadata={"reference_number": plan.reference_number, "status": status.value},
        )
        for row in result.dues_now_owed:
            if row.user_id is not None:
                self._notifications.notify_finance(
                    row.user_id,
                    None,
                    NotificationType.COD_DUES_OWED,
                    plan.source_type.value,
                    plan.source_id,
                    f"{row.dues_amount} {row.currency}",
                    plan.reference_number,
                )

    def _remove_stale(
        self, plan: SourcePlan, existing: dict[EarningBeneficiary, Earning], now: datetime
    ) -> bool:
        wanted = {entry.beneficiary_type for entry in plan.entries}
        changed = False
        for beneficiary, row in existing.items():
            if beneficiary in wanted or _is_locked(row):
                continue
            if row.status == EarningStatus.PENDING:
                self._earnings.delete(row)
                changed = True
            elif row.status == EarningStatus.AVAILABLE:
                row.status = EarningStatus.REVERSED
                row.reversed_at = now
                row.dues_status = None
                changed = True
        return changed

    def _new_row(self, plan: SourcePlan, entry: EntryPlan) -> Earning:
        return Earning(
            beneficiary_type=entry.beneficiary_type,
            source_type=plan.source_type,
            order_id=plan.source_id if plan.source_type == EarningSource.ORDER else None,
            booking_id=plan.source_id if plan.source_type == EarningSource.BOOKING else None,
            reference_number=plan.reference_number,
            currency=plan.currency,
            payment_mode=plan.payment_mode,
            status=EarningStatus.PENDING,
            gross_amount=entry.gross_amount,
            platform_fee_amount=entry.platform_fee_amount,
            commission_amount=entry.commission_amount,
            gateway_charge_amount=entry.gateway_charge_amount,
            net_amount=entry.net_amount,
            dues_amount=entry.dues_amount,
        )


def _native_admin_of(business: Business | None) -> UUID | None:
    if business is None or business.village is None:
        return None
    return business.village.native_admin_id


def _target_dues_status(row: Earning, status: EarningStatus) -> DuesStatus | None:
    owes = (
        row.beneficiary_type in SELLER_BENEFICIARIES
        and row.payment_mode == EarningPaymentMode.CASH
        and row.dues_amount > ZERO
        and status == EarningStatus.AVAILABLE
    )
    return DuesStatus.OWED if owes else None


def _update_row(
    row: Earning, plan: SourcePlan, entry: EntryPlan, now: datetime, result: SyncResult
) -> None:
    if _is_locked(row):
        return
    target_status = plan.status or row.status
    if row.status == EarningStatus.REVERSED:
        target_status = EarningStatus.REVERSED
    values: dict[str, object] = {"status": target_status}
    if row.status != EarningStatus.REVERSED:
        values.update(
            user_id=entry.user_id,
            business_id=entry.business_id,
            gross_amount=entry.gross_amount,
            platform_fee_amount=entry.platform_fee_amount,
            commission_amount=entry.commission_amount,
            gateway_charge_amount=entry.gateway_charge_amount,
            net_amount=entry.net_amount,
            dues_amount=entry.dues_amount,
            currency=plan.currency,
            payment_mode=plan.payment_mode,
        )
    for name, value in values.items():
        if getattr(row, name) != value:
            setattr(row, name, value)
            result.changed = True
    dues_status = _target_dues_status(row, target_status)
    if row.dues_status != dues_status:
        if dues_status == DuesStatus.OWED:
            result.dues_now_owed.append(row)
        row.dues_status = dues_status
        result.changed = True
    if target_status == EarningStatus.AVAILABLE and row.available_at is None:
        row.available_at = now
        result.changed = True
    if target_status == EarningStatus.REVERSED and row.reversed_at is None:
        row.reversed_at = now
        result.changed = True
