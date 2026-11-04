from datetime import datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.messages import DeliveryMessages
from app.models.delivery_settings import FEE_PRECISION, FEE_SCALE
from app.models.order import DeliveryOption
from app.schemas.base import BaseReadSchema

if TYPE_CHECKING:
    from app.models.delivery_settings import DeliverySettings

WEEKDAYS = range(1, 8)
DeliveryFee = Annotated[Decimal, Field(ge=0, max_digits=FEE_PRECISION, decimal_places=FEE_SCALE)]


class DeliverySettingsUpdate(BaseModel):
    working_days: list[int] = Field(min_length=1, max_length=len(WEEKDAYS))
    route_start_time: time
    route_end_time: time
    instant_fee: DeliveryFee | None = None
    route_fee: DeliveryFee | None = None

    @field_validator("working_days")
    @classmethod
    def _valid_weekdays(cls, days: list[int]) -> list[int]:
        if len(set(days)) != len(days) or any(day not in WEEKDAYS for day in days):
            raise ValueError(DeliveryMessages.WORKING_DAYS_INVALID)
        return sorted(days)

    @model_validator(mode="after")
    def _end_after_start(self) -> "DeliverySettingsUpdate":
        if self.route_end_time <= self.route_start_time:
            raise ValueError(DeliveryMessages.END_BEFORE_START)
        return self


class DeliverySettingsRead(BaseReadSchema):
    working_days: list[int]
    route_start_time: time
    route_end_time: time
    instant_fee: Decimal | None
    route_fee: Decimal | None
    updated_at: datetime

    @classmethod
    def from_settings(cls, settings: "DeliverySettings") -> "DeliverySettingsRead":
        return cls(
            working_days=list(settings.working_days),
            route_start_time=settings.route_start_time,
            route_end_time=settings.route_end_time,
            instant_fee=settings.instant_fee,
            route_fee=settings.route_fee,
            updated_at=settings.updated_at,
        )


class DeliveryOptionRead(BaseModel):
    option: DeliveryOption
    fee: Decimal
    available: bool
    working_days: list[int]
    window_start: time | None
    window_end: time | None
