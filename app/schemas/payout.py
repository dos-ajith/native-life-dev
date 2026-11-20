from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.messages import PayoutAccountMessages, PayoutMessages
from app.models.payment_status import PaymentStatus
from app.models.payout import PayeeType, PayoutMethod, PayoutStatus
from app.schemas.base import BaseReadSchema
from app.schemas.earning import EarningRead
from app.schemas.validators import NonBlankStr

ACCOUNT_NUMBER_PATTERN = r"^[0-9]{9,18}$"
IFSC_PATTERN = r"^[A-Z]{4}0[A-Z0-9]{6}$"
UPI_PATTERN = r"^[A-Za-z0-9._-]{2,256}@[A-Za-z]{2,64}$"
MASK = "••••"

HolderName = Annotated[NonBlankStr, Field(max_length=150)]
AccountNumber = Annotated[str, Field(pattern=ACCOUNT_NUMBER_PATTERN)]
Ifsc = Annotated[str, Field(pattern=IFSC_PATTERN)]
UpiId = Annotated[str, Field(pattern=UPI_PATTERN, max_length=100)]
PaymentReference = Annotated[NonBlankStr, Field(max_length=100)]
PayoutNote = Annotated[NonBlankStr, Field(max_length=500)]


class PayoutAccountWrite(BaseModel):
    account_holder_name: HolderName
    account_number: AccountNumber | None = None
    ifsc: Ifsc | None = None
    upi_id: UpiId | None = None

    @model_validator(mode="after")
    def _bank_or_upi(self) -> "PayoutAccountWrite":
        has_bank = self.account_number is not None and self.ifsc is not None
        partial_bank = (self.account_number is None) != (self.ifsc is None)
        if partial_bank or not (has_bank or self.upi_id):
            raise ValueError(PayoutAccountMessages.DETAILS_REQUIRED)
        return self


class PayoutAccountRead(BaseReadSchema):
    account_holder_name: str
    account_number_masked: str | None
    ifsc: str | None
    upi_id: str | None
    updated_at: datetime


def masked_account_number(last4: str | None) -> str | None:
    return f"{MASK}{last4}" if last4 else None


class PayoutDueQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_end: date | None = None
    payee_type: PayeeType | None = None


class PayoutDueRead(BaseModel):
    payee_type: PayeeType
    user_id: UUID | None
    business_id: UUID | None
    payee_name: str
    currency: str
    entry_count: int
    earnings_amount: Decimal
    dues_owed: Decimal
    payout_amount: Decimal
    has_payout_account: bool


class PayoutCreate(BaseModel):
    payee_type: PayeeType
    user_id: UUID | None = None
    business_id: UUID | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    period_end: date | None = None

    @model_validator(mode="after")
    def _payee_identified(self) -> "PayoutCreate":
        if self.payee_type == PayeeType.BUSINESS and self.business_id is None:
            raise ValueError(PayoutMessages.PAYEE_INVALID)
        if self.payee_type != PayeeType.BUSINESS and self.user_id is None:
            raise ValueError(PayoutMessages.PAYEE_INVALID)
        return self


class PayoutBulkCreate(BaseModel):
    period_end: date | None = None
    payee_type: PayeeType | None = None


class PayoutMarkPaid(BaseModel):
    payment_reference: PaymentReference
    paid_at: datetime | None = None
    note: PayoutNote | None = None


class PayoutListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: PayoutStatus | None = None
    payee_type: PayeeType | None = None
    business_id: UUID | None = None
    user_id: UUID | None = None


class PayoutRead(BaseReadSchema):
    id: UUID
    payout_number: str
    payee_type: PayeeType
    user_id: UUID | None
    business_id: UUID | None
    payee_name: str = ""
    period_end: date
    earnings_amount: Decimal
    dues_offset_amount: Decimal
    payout_amount: Decimal
    currency: str
    status: PayoutStatus
    method: PayoutMethod | None
    payment_reference: str | None
    failure_reason: str | None
    note: str | None
    paid_at: datetime | None
    created_at: datetime


class PayoutDetailRead(PayoutRead):
    payout_account: PayoutAccountRead | None
    earnings: list[EarningRead]


class DuesPaymentRead(BaseReadSchema):
    id: UUID
    user_id: UUID | None
    business_id: UUID | None
    status: PaymentStatus
    payment_url: str
    total_amount: Decimal
    currency: str
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime


class DuesSummaryRead(BaseModel):
    currency: str
    total_owed: Decimal
    entries: list[EarningRead]
    pending_payment: DuesPaymentRead | None


class DuesOwedRead(BaseModel):
    payee_type: PayeeType
    user_id: UUID | None
    business_id: UUID | None
    payee_name: str
    currency: str
    entry_count: int
    total_owed: Decimal
