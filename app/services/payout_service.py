import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import get_settings
from app.core.encryption import FieldCipher
from app.core.exceptions import (
    AuthenticationError,
    BusinessRuleError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.messages import PayoutMessages
from app.core.payouts import FundAccountRequest, PayoutGateway, PayoutRequest
from app.core.timezone import app_now, to_naive_app_time
from app.models.earning import DuesStatus, Earning, EarningStatus
from app.models.notification import NotificationType
from app.models.payout import PayeeType, Payout, PayoutMethod, PayoutStatus
from app.models.payout_account import PayoutAccount
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.earning_repository import EarningRepository
from app.repositories.payout_repository import PayoutAccountRepository, PayoutRepository
from app.repositories.user_repository import UserRepository
from app.schemas.earning import EarningRead
from app.schemas.pagination import PaginationParams
from app.schemas.payout import (
    PayoutBulkCreate,
    PayoutCreate,
    PayoutDetailRead,
    PayoutDueQuery,
    PayoutDueRead,
    PayoutListQuery,
    PayoutMarkPaid,
    PayoutRead,
)
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService
from app.services.business_verification_service import SPREADSHEET_FORMULA_PREFIXES
from app.services.notification_service import NotificationService
from app.services.payees import PayeeKey, payee_filter, payee_key
from app.services.payment_links import minor_units
from app.services.payout_account_service import account_read

ENTITY_TYPE = "payout"
ZERO = Decimal(0)
ONE_DAY = timedelta(days=1)
PROCESSED_EVENT = "payout.processed"
FAILED_EVENTS = frozenset({"payout.failed", "payout.reversed", "payout.rejected"})
EXPORT_COLUMNS = (
    "payout_number",
    "payee_type",
    "payee_name",
    "account_holder_name",
    "account_number",
    "ifsc",
    "upi_id",
    "amount",
    "currency",
)


@dataclass
class DueTotals:
    entry_count: int = 0
    earnings: Decimal = ZERO
    dues: Decimal = ZERO


def _cutoff(period_end: date | None) -> tuple[date, datetime]:
    end = period_end or app_now().date()
    return end, datetime.combine(end + ONE_DAY, time.min)


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(SPREADSHEET_FORMULA_PREFIXES) else text


class PayoutService:
    def __init__(self, db: Session, gateway: PayoutGateway | None = None) -> None:
        self._gateway = gateway
        self._earnings = EarningRepository(db)
        self._payouts = PayoutRepository(db)
        self._accounts = PayoutAccountRepository(db)
        self._businesses = BusinessRepository(db)
        self._business_access = BusinessService(db)
        self._users = UserRepository(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def due(self, query: PayoutDueQuery) -> list[PayoutDueRead]:
        _, before = _cutoff(query.period_end)
        totals: dict[PayeeKey, DueTotals] = defaultdict(DueTotals)
        for row in self._earnings.payable(before):
            key = payee_key(row)
            if key is not None:
                totals[key].entry_count += 1
                totals[key].earnings += row.net_amount
        for row in self._earnings.dues_owed(unlinked=True):
            key = payee_key(row)
            if key is not None:
                totals[key].entry_count += 1
                totals[key].dues += row.dues_amount
        reads = [
            self._due_read(key, total)
            for key, total in totals.items()
            if query.payee_type is None or key.payee_type == query.payee_type
        ]
        return sorted(reads, key=lambda read: read.payout_amount, reverse=True)

    def create(self, payload: PayoutCreate, actor: User) -> PayoutRead:
        payout = self._create_draft(payload, actor)
        self._payouts.commit()
        self._log(actor, ActivityAction.PAYOUT_CREATED, payout)
        return self._read(payout)

    def create_all(self, payload: PayoutBulkCreate, actor: User) -> list[PayoutRead]:
        created: list[Payout] = []
        for due in self.due(
            PayoutDueQuery(period_end=payload.period_end, payee_type=payload.payee_type)
        ):
            if due.payout_amount <= ZERO:
                continue
            request = PayoutCreate(
                payee_type=due.payee_type,
                user_id=due.user_id,
                business_id=due.business_id,
                currency=due.currency,
                period_end=payload.period_end,
            )
            created.append(self._create_draft(request, actor))
        self._payouts.commit()
        for payout in created:
            self._log(actor, ActivityAction.PAYOUT_CREATED, payout)
        return [self._read(payout) for payout in created]

    def mark_paid(self, payout_id: UUID, payload: PayoutMarkPaid, actor: User) -> PayoutRead:
        payout = self._draft(payout_id)
        payout.note = payload.note
        paid_at = to_naive_app_time(payload.paid_at) if payload.paid_at else None
        self._finalize(payout, PayoutMethod.MANUAL, payload.payment_reference, actor.id, paid_at)
        self._payouts.commit()
        self._log(actor, ActivityAction.PAYOUT_PAID, payout)
        self._notify_paid(payout)
        return self._read(payout)

    def send(self, payout_id: UUID, actor: User) -> PayoutRead:
        gateway = self._require_gateway()
        payout = self._draft(payout_id)
        account = self._account_for(payout)
        if account is None:
            raise BusinessRuleError(PayoutMessages.NO_ACCOUNT)
        if account.razorpayx_fund_account_id is None:
            fund = gateway.create_fund_account(self._fund_request(account, payout))
            account.razorpayx_contact_id = fund.contact_id
            account.razorpayx_fund_account_id = fund.fund_account_id
            self._payouts.commit()
            payout = self._draft(payout_id)
        created = gateway.create_payout(
            PayoutRequest(
                fund_account_id=str(account.razorpayx_fund_account_id),
                amount_minor=minor_units(payout.payout_amount),
                currency=payout.currency,
                uses_upi=account.account_number_encrypted is None,
                reference=payout.payout_number,
                narration=payout.payout_number,
                idempotency_key=str(payout.id),
            )
        )
        payout.status = PayoutStatus.PROCESSING
        payout.method = PayoutMethod.RAZORPAYX
        payout.provider_payout_id = created.payout_id
        payout.paid_by = actor.id
        self._payouts.commit()
        self._log(actor, ActivityAction.PAYOUT_SENT, payout)
        return self._read(payout)

    def record_webhook(self, body: bytes, signature: str) -> None:
        if not self._require_gateway().webhook_is_authentic(body, signature):
            raise AuthenticationError(PayoutMessages.WEBHOOK_INVALID)
        event: dict[str, Any] = json.loads(body)
        name = event.get("event")
        entity = event.get("payload", {}).get("payout", {}).get("entity", {})
        payout = self._payouts.get_by_provider_id(str(entity.get("id", "")))
        if payout is None:
            self._payouts.rollback()
            return
        if name == PROCESSED_EVENT and payout.status == PayoutStatus.PROCESSING:
            reference = entity.get("utr") or payout.provider_payout_id
            self._finalize(payout, PayoutMethod.RAZORPAYX, str(reference), payout.paid_by, None)
            self._payouts.commit()
            self._log(None, ActivityAction.PAYOUT_PAID, payout)
            self._notify_paid(payout)
        elif name in FAILED_EVENTS and payout.status in (
            PayoutStatus.PROCESSING,
            PayoutStatus.PAID,
        ):
            self._release(payout)
            payout.status = PayoutStatus.FAILED
            payout.failure_reason = str(entity.get("failure_reason") or name)
            self._payouts.commit()
            self._log(None, ActivityAction.PAYOUT_FAILED, payout)
        else:
            self._payouts.rollback()

    def cancel(self, payout_id: UUID, actor: User) -> PayoutRead:
        payout = self._draft(payout_id)
        self._release(payout)
        payout.status = PayoutStatus.CANCELLED
        self._payouts.commit()
        self._log(actor, ActivityAction.PAYOUT_CANCELLED, payout)
        return self._read(payout)

    def list_all(
        self, query: PayoutListQuery, params: PaginationParams
    ) -> tuple[list[PayoutRead], int]:
        filters: list[ColumnElement[bool]] = []
        if query.status is not None:
            filters.append(Payout.status == query.status)
        if query.payee_type is not None:
            filters.append(Payout.payee_type == query.payee_type)
        if query.business_id is not None:
            filters.append(Payout.business_id == query.business_id)
        if query.user_id is not None:
            filters.append(Payout.user_id == query.user_id)
        return self._page(filters, params)

    def list_mine(self, actor: User, params: PaginationParams) -> tuple[list[PayoutRead], int]:
        return self._page(
            [Payout.user_id == actor.id, Payout.payee_type != PayeeType.BUSINESS], params
        )

    def list_for_business(
        self, business_id: UUID, actor: User, params: PaginationParams
    ) -> tuple[list[PayoutRead], int]:
        business = self._business_access.get_for_actor(business_id, actor)
        return self._page([Payout.business_id == business.id], params)

    def get(self, payout_id: UUID) -> PayoutDetailRead:
        payout = self._payouts.get(payout_id)
        if payout is None:
            raise NotFoundError(PayoutMessages.NOT_FOUND)
        account = self._account_for(payout)
        read = self._read(payout)
        return PayoutDetailRead(
            **{name: getattr(read, name) for name in PayoutRead.model_fields},
            payout_account=account_read(account) if account is not None else None,
            earnings=[
                EarningRead.model_validate(row) for row in self._earnings.for_payout(payout.id)
            ],
        )

    def export_csv(self, query: PayoutListQuery) -> str:
        cipher = FieldCipher.from_settings(get_settings())
        status_query = (
            query if query.status else query.model_copy(update={"status": PayoutStatus.DRAFT})
        )
        payouts, _ = self.list_all(status_query, PaginationParams(page=1, page_size=10_000))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(EXPORT_COLUMNS)
        for read in payouts:
            payout = self._payouts.get(read.id)
            account = self._account_for(payout) if payout is not None else None
            number = (
                cipher.decrypt(account.account_number_encrypted)
                if account is not None and account.account_number_encrypted
                else None
            )
            writer.writerow(
                _csv_cell(value)
                for value in (
                    read.payout_number,
                    read.payee_type.value,
                    read.payee_name,
                    account.account_holder_name if account else None,
                    number,
                    account.ifsc if account else None,
                    account.upi_id if account else None,
                    read.payout_amount,
                    read.currency,
                )
            )
        return buffer.getvalue()

    def _create_draft(self, payload: PayoutCreate, actor: User) -> Payout:
        period_end, before = _cutoff(payload.period_end)
        payee = payee_filter(
            payload.payee_type, payload.user_id, payload.business_id, payload.currency
        )
        payable = self._earnings.payable(before, payee, lock=True)
        owed = self._earnings.dues_owed(payee, lock=True, unlinked=True)
        earnings_amount = sum((row.net_amount for row in payable), ZERO)
        dues = sum((row.dues_amount for row in owed), ZERO)
        if earnings_amount - dues <= ZERO:
            self._payouts.rollback()
            raise BusinessRuleError(PayoutMessages.NOTHING_DUE)
        payout = self._payouts.add(
            Payout(
                payout_number=self._payouts.next_number(),
                payee_type=payload.payee_type,
                user_id=self._payee_user_id(payload),
                business_id=payload.business_id,
                period_end=period_end,
                earnings_amount=earnings_amount,
                dues_offset_amount=dues,
                payout_amount=earnings_amount - dues,
                currency=payload.currency,
                status=PayoutStatus.DRAFT,
                created_by=actor.id,
            )
        )
        for row in (*payable, *owed):
            row.payout_id = payout.id
        return payout

    def _finalize(
        self,
        payout: Payout,
        method: PayoutMethod,
        reference: str,
        paid_by: UUID | None,
        paid_at: datetime | None,
    ) -> None:
        now = to_naive_app_time(app_now())
        payout.status = PayoutStatus.PAID
        payout.method = method
        payout.payment_reference = reference
        payout.paid_by = paid_by
        payout.paid_at = paid_at or now
        for row in self._earnings.for_payout(payout.id):
            if row.dues_status == DuesStatus.OWED:
                row.dues_status = DuesStatus.OFFSET
            else:
                row.status = EarningStatus.SETTLED
                row.settled_at = now

    def _release(self, payout: Payout) -> None:
        for row in self._earnings.for_payout(payout.id):
            _release_row(row)

    def _draft(self, payout_id: UUID) -> Payout:
        payout = self._payouts.get(payout_id, lock=True)
        if payout is None:
            raise NotFoundError(PayoutMessages.NOT_FOUND)
        if payout.status != PayoutStatus.DRAFT:
            self._payouts.rollback()
            raise BusinessRuleError(PayoutMessages.NOT_DRAFT)
        return payout

    def _account_for(self, payout: Payout) -> PayoutAccount | None:
        if payout.payee_type == PayeeType.BUSINESS and payout.business_id is not None:
            return self._accounts.for_business(payout.business_id)
        if payout.user_id is not None:
            return self._accounts.personal(payout.user_id)
        return None

    def _fund_request(self, account: PayoutAccount, payout: Payout) -> FundAccountRequest:
        number = None
        if account.account_number_encrypted:
            number = FieldCipher.from_settings(get_settings()).decrypt(
                account.account_number_encrypted
            )
        return FundAccountRequest(
            reference=str(account.id),
            holder_name=account.account_holder_name,
            account_number=number,
            ifsc=account.ifsc,
            upi_id=account.upi_id,
        )

    def _payee_user_id(self, payload: PayoutCreate) -> UUID | None:
        if payload.payee_type != PayeeType.BUSINESS:
            return payload.user_id
        business = self._businesses.get_by_id(payload.business_id) if payload.business_id else None
        return business.owner_id if business is not None else None

    def _due_read(self, key: PayeeKey, total: DueTotals) -> PayoutDueRead:
        if key.payee_type == PayeeType.BUSINESS and key.business_id is not None:
            account = self._accounts.for_business(key.business_id)
        else:
            account = self._accounts.personal(key.user_id) if key.user_id else None
        return PayoutDueRead(
            payee_type=key.payee_type,
            user_id=key.user_id,
            business_id=key.business_id,
            payee_name=self._payee_name(key.payee_type, key.user_id, key.business_id),
            currency=key.currency,
            entry_count=total.entry_count,
            earnings_amount=total.earnings,
            dues_owed=total.dues,
            payout_amount=total.earnings - total.dues,
            has_payout_account=account is not None,
        )

    def _payee_name(
        self, payee_type: PayeeType, user_id: UUID | None, business_id: UUID | None
    ) -> str:
        if payee_type == PayeeType.BUSINESS and business_id is not None:
            business = self._businesses.get_by_id(business_id)
            return business.name if business is not None else ""
        user = self._users.get_by_id(user_id) if user_id is not None else None
        return f"{user.first_name} {user.last_name}".strip() if user is not None else ""

    def _read(self, payout: Payout) -> PayoutRead:
        read = PayoutRead.model_validate(payout)
        read.payee_name = self._payee_name(payout.payee_type, payout.user_id, payout.business_id)
        return read

    def _page(
        self, filters: list[ColumnElement[bool]], params: PaginationParams
    ) -> tuple[list[PayoutRead], int]:
        rows, total = self._payouts.page(filters, params)
        return [self._read(row) for row in rows], total

    def _notify_paid(self, payout: Payout) -> None:
        if payout.user_id is None:
            return
        self._notifications.notify_finance(
            payout.user_id,
            payout.paid_by,
            NotificationType.PAYOUT_PAID,
            ENTITY_TYPE,
            payout.id,
            f"{payout.payout_amount} {payout.currency}",
            payout.payout_number,
        )

    def _require_gateway(self) -> PayoutGateway:
        if self._gateway is None:
            raise ServiceUnavailableError(PayoutMessages.RAZORPAYX_DISABLED)
        return self._gateway

    def _log(self, actor: User | None, action: str, payout: Payout) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=payout.id,
            metadata={
                "payout_number": payout.payout_number,
                "payee_type": payout.payee_type.value,
                "payout_amount": str(payout.payout_amount),
                "status": payout.status.value,
            },
        )


def _release_row(row: Earning) -> None:
    row.payout_id = None
    if row.dues_status == DuesStatus.OFFSET:
        row.dues_status = DuesStatus.OWED
    if row.status == EarningStatus.SETTLED:
        row.status = EarningStatus.AVAILABLE
        row.settled_at = None
