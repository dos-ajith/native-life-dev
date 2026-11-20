from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.delivery_request import DeliveryRequestStatus
from app.models.order import DeliveryOption
from app.schemas.base import BaseReadSchema
from app.schemas.delivery_route import GeoPoint
from app.schemas.delivery_vehicle import DeliveryVehicleRead


class CourierPromoterRead(BaseModel):
    id: UUID
    name: str
    phone: str | None


class CourierProfileRead(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    promoter: CourierPromoterRead | None
    vehicle: DeliveryVehicleRead | None


class CourierRequestListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: DeliveryRequestStatus | None = None
    delivery_date: date | None = None


class CourierRequestRead(BaseReadSchema):
    id: UUID
    order_id: UUID
    order_number: str
    option: DeliveryOption
    status: DeliveryRequestStatus
    delivery_date: date
    route_id: UUID | None
    route_name: str | None
    customer_name: str
    customer_phone: str | None
    shipping_address: str | None
    destination: GeoPoint | None
    started_at: datetime | None
    delivered_at: datetime | None
    proof_available: bool
