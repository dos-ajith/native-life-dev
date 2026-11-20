from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.messages import BookingMessages
from app.models.booking import (
    CUSTOMER_NAME_LENGTH,
    CUSTOMER_PHONE_LENGTH,
    NOTE_LENGTH,
    Booking,
    BookingStatus,
)
from app.models.payment_status import PaymentStatus
from app.schemas.base import BaseReadSchema
from app.schemas.validators import NonBlankStr

MAX_PARTY_SIZE = 100

CustomerName = Annotated[NonBlankStr, Field(max_length=CUSTOMER_NAME_LENGTH)]
CustomerPhone = Annotated[NonBlankStr, Field(max_length=CUSTOMER_PHONE_LENGTH)]
Note = Annotated[NonBlankStr, Field(max_length=NOTE_LENGTH)]


class BookingCreate(BaseModel):
    item_id: UUID
    start_date: date
    end_date: date | None = None
    party_size: Annotated[int, Field(ge=1, le=MAX_PARTY_SIZE)]
    customer_name: CustomerName
    customer_phone: CustomerPhone
    note: Note | None = None

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError(BookingMessages.END_BEFORE_START)
        return self


class BookingReject(BaseModel):
    note: Note


class BookingCancel(BaseModel):
    reason: Note | None = None


class BookingListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: BookingStatus | None = None


class BookingPaymentRead(BaseReadSchema):
    id: UUID
    booking_id: UUID
    provider: str
    status: PaymentStatus
    payment_url: str
    unit_price: Decimal
    party_size: int
    subtotal: Decimal
    tax_percent: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    expires_at: datetime
    paid_at: datetime | None


class BookingRead(BaseReadSchema):
    id: UUID
    booking_number: str
    business_id: UUID
    customer_id: UUID
    plugin_key: str
    item_id: UUID
    item_name: str
    status: BookingStatus
    start_date: date
    end_date: date | None
    party_size: int
    customer_name: str
    customer_phone: str
    note: str | None
    original_price: Decimal | None
    unit_price: Decimal
    tax_percent: Decimal
    currency: str
    platform_fee_percent: Decimal
    platform_fee_amount: Decimal
    commission_percent: Decimal
    commission_amount: Decimal
    gateway_charge_percent: Decimal
    payment: BookingPaymentRead | None
    response_note: str | None
    responded_at: datetime | None
    created_at: datetime

    @classmethod
    def from_booking(cls, booking: Booking) -> Self:
        return cls.model_validate(booking)
