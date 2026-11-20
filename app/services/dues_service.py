from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, and_
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ServiceUnavailableError
from app.core.messages import DuesMessages, PaymentMessages
from app.core.payments import PaymentGateway, PaymentLinkRequest
from app.core.timezone import app_now, to_naive_app_time
from app.models.dues_payment import DuesPayment
from app.models.earning import DuesStatus, Earning, EarningBeneficiary
from app.models.notification import NotificationType
from app.models.payment_status import PaymentStatus
from app.models.payout import PayeeType
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.earning_repository import EarningRepository
from app.repositories.payout_repository import DuesPaymentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.earning import EarningRead
from app.schemas.pagination import PaginationParams
from app.schemas.payment import PaymentStatusRead
from app.schemas.payout import DuesOwedRead, DuesPaymentRead, DuesSummaryRead
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService
from app.services.notification_service import NotificationService
from app.services.payees import payee_key
from app.services.payment_links import link_expires_at, minor_units, settled_status

ENTITY_TYPE = "dues_payment"
ZERO = Decimal(0)
DEFAULT_CURRENCY = "INR"
REFERENCE_PREFIX = "DUES-"
REFERENCE_MAX_LENGTH = 40


@dataclass(frozen=True)
class DuesPayer:
    user_id: UUID | None
    business_id: UUID | None
    earnings_scope: ColumnElement[bool]
    payment_scope: ColumnElement[bool]
    name: str
    phone: str | None


@dataclass
class OwedTotals:
    entry_count: int = 0
    total: Decimal = ZERO


class DuesService:
    def __init__(self, db: Session, gateway: PaymentGateway | None = None) -> None:
        self._gateway = gateway
        self._earnings = EarningRepository(db)
        self._payments = DuesPaymentRepository(db)
        self._businesses = BusinessRepository(db)
        self._business_access = BusinessService(db)
        self._users = UserRepository(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def summary_mine(self, actor: User) -> DuesSummaryRead:
        return self._summary(self._personal_payer(actor))

    def summary_for_business(self, business_id: UUID, actor: User) -> DuesSummaryRead:
        return self._summary(self._business_payer(business_id, actor))

    def pay_mine(self, actor: User) -> DuesPaymentRead:
        return self._pay(self._personal_payer(actor), actor)

    def pay_for_business(self, business_id: UUID, actor: User) -> DuesPaymentRead:
        return self._pay(self._business_payer(business_id, actor), actor)

    def owed_by_payee(self) -> list[DuesOwedRead]:
        totals: dict[tuple[PayeeType, UUID | None, UUID | None, str], OwedTotals] = defaultdict(
            OwedTotals
        )
        for row in self._earnings.dues_owed():
            key = payee_key(row)
            if key is None:
                continue
            bucket = totals[(key.payee_type, key.user_id, key.business_id, key.currency)]
            bucket.entry_count += 1
            bucket.total += row.dues_amount
        return [
            DuesOwedRead(
                payee_type=payee_type,
                user_id=user_id,
                business_id=business_id,
                payee_name=self._payee_name(user_id, business_id),
                currency=currency,
                entry_count=bucket.entry_count,
                total_owed=bucket.total,
            )
            for (payee_type, user_id, business_id, currency), bucket in totals.items()
        ]

    def list_payments(self, params: PaginationParams) -> tuple[list[DuesPaymentRead], int]:
        rows, total = self._payments.page(params)
        return [DuesPaymentRead.model_validate(row) for row in rows], total

    def settle_link(
        self,
        link_id: str,
        gateway_status: str,
        provider_payment_id: str | None,
        actor: User | None,
    ) -> PaymentStatusRead | None:
        payment = self._payments.get_by_link_id(link_id)
        if payment is None:
            return None
        target = settled_status(gateway_status)
        paid_at = to_naive_app_time(app_now()) if target == PaymentStatus.PAID else None
        if target is None or not self._payments.settle_pending(
            payment, target, provider_payment_id, paid_at
        ):
            self._payments.rollback()
            return _status_read(payment)
        for row in self._earnings.for_dues_payment(payment.id):
            if target == PaymentStatus.PAID:
                row.dues_status = DuesStatus.PAID
            else:
                row.dues_payment_id = None
        self._payments.commit()
        action = (
            ActivityAction.DUES_PAID
            if target == PaymentStatus.PAID
            else ActivityAction.DUES_PAYMENT_EXPIRED
        )
        self._log(actor, action, payment)
        if target == PaymentStatus.PAID and payment.user_id is not None:
            self._notifications.notify_finance(
                payment.user_id,
                None,
                NotificationType.DUES_PAID,
                ENTITY_TYPE,
                payment.id,
                f"{payment.total_amount} {payment.currency}",
            )
        return _status_read(payment)

    def send_statements(self) -> int:
        sent = 0
        for owed in self.owed_by_payee():
            recipient = owed.user_id
            if owed.payee_type == PayeeType.BUSINESS and owed.business_id is not None:
                business = self._businesses.get_by_id(owed.business_id)
                recipient = business.owner_id if business is not None else None
            if recipient is None or owed.total_owed <= ZERO:
                continue
            self._notifications.notify_finance(
                recipient,
                None,
                NotificationType.DUES_STATEMENT,
                ENTITY_TYPE,
                owed.business_id or recipient,
                f"{owed.total_owed} {owed.currency}",
            )
            sent += 1
        self._payments.commit()
        return sent

    def _summary(self, payer: DuesPayer) -> DuesSummaryRead:
        rows = self._earnings.dues_owed(payer.earnings_scope)
        pending = self._payments.pending_for(payer.payment_scope)
        return DuesSummaryRead(
            currency=rows[0].currency if rows else DEFAULT_CURRENCY,
            total_owed=sum((row.dues_amount for row in rows), ZERO),
            entries=[EarningRead.model_validate(row) for row in rows],
            pending_payment=DuesPaymentRead.model_validate(pending) if pending else None,
        )

    def _pay(self, payer: DuesPayer, actor: User) -> DuesPaymentRead:
        pending = self._payments.pending_for(payer.payment_scope)
        if pending is not None and pending.expires_at > to_naive_app_time(app_now()):
            return DuesPaymentRead.model_validate(pending)
        gateway = self._require_gateway()
        rows = self._earnings.dues_owed(payer.earnings_scope, lock=True, unlinked=True)
        total = sum((row.dues_amount for row in rows), ZERO)
        if total <= ZERO:
            self._payments.rollback()
            raise BusinessRuleError(DuesMessages.NOTHING_OWED)
        currency = rows[0].currency
        expires_at = link_expires_at()
        reference = f"{REFERENCE_PREFIX}{payer.business_id or payer.user_id}"[:REFERENCE_MAX_LENGTH]
        link = gateway.create_link(
            PaymentLinkRequest(
                reference=reference,
                amount_minor=minor_units(total),
                currency=currency,
                description=DuesMessages.LINK_DESCRIPTION.format(amount=f"{total} {currency}"),
                customer_name=payer.name,
                customer_phone=payer.phone or "",
                expires_at=expires_at,
                notes={"dues_payer": str(payer.business_id or payer.user_id)},
            )
        )
        payment = self._payments.add(
            DuesPayment(
                user_id=payer.user_id,
                business_id=payer.business_id,
                provider=gateway.name,
                provider_link_id=link.link_id,
                payment_url=link.url,
                total_amount=total,
                currency=currency,
                status=PaymentStatus.PENDING,
                expires_at=to_naive_app_time(expires_at),
            )
        )
        for row in rows:
            row.dues_payment_id = payment.id
        self._payments.commit()
        self._log(actor, ActivityAction.DUES_PAYMENT_LINK_CREATED, payment)
        return DuesPaymentRead.model_validate(payment)

    def _personal_payer(self, actor: User) -> DuesPayer:
        return DuesPayer(
            user_id=actor.id,
            business_id=None,
            earnings_scope=and_(
                Earning.user_id == actor.id,
                Earning.beneficiary_type == EarningBeneficiary.INDIVIDUAL_SELLER,
            ),
            payment_scope=and_(DuesPayment.user_id == actor.id, DuesPayment.business_id.is_(None)),
            name=f"{actor.first_name} {actor.last_name}".strip(),
            phone=actor.phone,
        )

    def _business_payer(self, business_id: UUID, actor: User) -> DuesPayer:
        business = self._business_access.get_for_actor(business_id, actor)
        owner = self._users.get_by_id(business.owner_id)
        return DuesPayer(
            user_id=business.owner_id,
            business_id=business.id,
            earnings_scope=and_(
                Earning.business_id == business.id,
                Earning.beneficiary_type == EarningBeneficiary.BUSINESS,
            ),
            payment_scope=DuesPayment.business_id == business.id,
            name=business.name,
            phone=owner.phone if owner is not None else None,
        )

    def _payee_name(self, user_id: UUID | None, business_id: UUID | None) -> str:
        if business_id is not None:
            business = self._businesses.get_by_id(business_id)
            return business.name if business is not None else ""
        user = self._users.get_by_id(user_id) if user_id is not None else None
        return f"{user.first_name} {user.last_name}".strip() if user is not None else ""

    def _require_gateway(self) -> PaymentGateway:
        if self._gateway is None:
            raise ServiceUnavailableError(PaymentMessages.GATEWAY_DISABLED)
        return self._gateway

    def _log(self, actor: User | None, action: str, payment: DuesPayment) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=payment.id,
            metadata={
                "business_id": str(payment.business_id) if payment.business_id else None,
                "total_amount": str(payment.total_amount),
                "status": payment.status.value,
            },
        )


def _status_read(payment: DuesPayment) -> PaymentStatusRead:
    return PaymentStatusRead.from_dues_payment(payment)
