from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import DeliveryOption
from app.schemas.ai_draft import AIDraftDetails
from app.schemas.deal import (
    MAX_DEAL_ITEMS,
    DealDeliveryDetails,
    DealDescription,
    DealItemDescription,
    DealItemName,
    DealName,
    DealPickupLocation,
    DealUnit,
    Price,
    Quantity,
)

MISSING_PICKUP_OR_DELIVERY = "pickup_location_or_delivery_details"


class AIDealItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: DealItemName
    description: DealItemDescription | None = None
    unit: DealUnit | None = None
    quantity: Quantity | None = None
    original_price: Price | None = None
    deal_price: Price | None = None


class DealDraftDetails(AIDraftDetails):
    model_config = ConfigDict(extra="forbid")

    name: DealName | None = None
    category_id: UUID | None = None
    description: DealDescription | None = None
    min_joiners: Quantity | None = None
    starts_at: datetime | None = None
    valid_until: datetime | None = None
    pickup_location: DealPickupLocation | None = None
    delivery_details: DealDeliveryDetails | None = None
    delivery_options: list[DeliveryOption] | None = Field(default=None, min_length=1)
    items: list[AIDealItem] | None = Field(default=None, min_length=1, max_length=MAX_DEAL_ITEMS)

    def missing_fields(self) -> list[str]:
        required = ("name", "category_id", "starts_at", "valid_until", "delivery_options", "items")
        missing = [field for field in required if getattr(self, field) is None]
        if self.pickup_location is None and self.delivery_details is None:
            missing.append(MISSING_PICKUP_OR_DELIVERY)
        if (
            self.delivery_options is not None
            and DeliveryOption.SELF_PICKUP in self.delivery_options
            and self.pickup_location is None
        ):
            missing.append("pickup_location")
        return missing
