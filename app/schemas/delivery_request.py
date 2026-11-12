from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.delivery_request import DeliveryRequestStatus
from app.models.delivery_vehicle import VehicleType
from app.models.order import DeliveryOption, OrderStatus
from app.schemas.base import BaseReadSchema
from app.schemas.delivery_route import GeoPoint
from app.schemas.post import Latitude, Longitude


class DeliveryRequestAccept(BaseModel):
    route_id: UUID | None = None


class DeliveryReRequest(BaseModel):
    route_id: UUID | None = None


class DeliveryRequestListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: DeliveryRequestStatus = DeliveryRequestStatus.REQUESTED


class DeliveryStopsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    delivery_date: date | None = None


class EligibleRouteRead(BaseModel):
    route_id: UUID
    route_name: str
    promoter_id: UUID
    promoter_name: str
    vehicle_type: VehicleType | None
    vehicle_name: str | None
    option: DeliveryOption
    fee: Decimal
    delivery_date: date


class NearbyRouteRead(EligibleRouteRead):
    start: GeoPoint
    end: GeoPoint
    path: list[GeoPoint] | None
    coverage_radius_m: int
    coverage: list[GeoPoint]


class NearMissRouteRead(EligibleRouteRead):
    meters_outside: int


class RiderLocationRead(BaseReadSchema):
    location: GeoPoint
    updated_at: datetime


class DeliveryRequestRead(BaseReadSchema):
    id: UUID
    order_id: UUID
    order_number: str
    option: DeliveryOption
    status: DeliveryRequestStatus
    delivery_date: date
    expires_at: datetime
    decided_at: datetime | None
    fee: Decimal
    route_id: UUID | None
    route_name: str | None
    promoter_id: UUID | None
    promoter_name: str | None
    customer_name: str
    shipping_address: str | None
    destination: GeoPoint | None
    open_for_claim: bool = False
    rider_location: RiderLocationRead | None = None


class DeliveryStopRead(BaseReadSchema):
    request_id: UUID
    request_status: DeliveryRequestStatus
    order_id: UUID
    order_number: str
    order_status: OrderStatus
    customer_name: str
    customer_phone: str | None
    shipping_address: str | None
    destination: GeoPoint | None


class EligibleRouteListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    option: DeliveryOption
    address_id: UUID
    deal_id: UUID | None = None


class NearbyRouteListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    option: DeliveryOption
    latitude: Latitude
    longitude: Longitude


class NearMissRouteListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    option: DeliveryOption
    address_id: UUID
