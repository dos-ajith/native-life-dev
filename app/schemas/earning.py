from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.messages import EarningMessages
from app.models.earning import (
    DuesStatus,
    EarningBeneficiary,
    EarningPaymentMode,
    EarningSource,
    EarningStatus,
)
from app.schemas.base import BaseReadSchema


class EarningListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: EarningStatus | None = None
    source_type: EarningSource | None = None
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _ordered_dates(self) -> "EarningListQuery":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError(EarningMessages.DATE_RANGE_INVALID)
        return self


class AdminEarningListQuery(EarningListQuery):
    beneficiary_type: EarningBeneficiary | None = None
    business_id: UUID | None = None
    user_id: UUID | None = None


class EarningRead(BaseReadSchema):
    id: UUID
    beneficiary_type: EarningBeneficiary
    user_id: UUID | None
    business_id: UUID | None
    source_type: EarningSource
    order_id: UUID | None
    booking_id: UUID | None
    reference_number: str
    gross_amount: Decimal
    platform_fee_amount: Decimal
    commission_amount: Decimal
    gateway_charge_amount: Decimal
    net_amount: Decimal
    dues_amount: Decimal
    dues_status: DuesStatus | None
    payout_id: UUID | None
    currency: str
    payment_mode: EarningPaymentMode
    status: EarningStatus
    available_at: datetime | None
    reversed_at: datetime | None
    settled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EarningTotalsRead(BaseModel):
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


class EarningSummaryRead(BaseModel):
    totals: list[EarningTotalsRead]
