from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.delivery_route import ROUTE_NAME_LENGTH
from app.schemas.base import BaseReadSchema
from app.schemas.delivery_vehicle import DeliveryVehicleRead
from app.schemas.post import Latitude, Longitude
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.delivery_route import DeliveryRoute

MIN_COVERAGE_RADIUS_M = 100
MAX_COVERAGE_RADIUS_M = 20000

MIN_PATH_POINTS = 2
MAX_PATH_POINTS = 5000

RouteName = Annotated[NonBlankStr, Field(max_length=ROUTE_NAME_LENGTH)]
CoverageRadius = Annotated[int, Field(ge=MIN_COVERAGE_RADIUS_M, le=MAX_COVERAGE_RADIUS_M)]


class GeoPoint(BaseModel):
    latitude: Latitude
    longitude: Longitude


RoutePath = Annotated[list[GeoPoint], Field(min_length=MIN_PATH_POINTS, max_length=MAX_PATH_POINTS)]


class DeliveryRouteCreate(BaseModel):
    name: RouteName
    start_point: GeoPoint
    end_point: GeoPoint
    path: RoutePath | None = None
    coverage_radius_m: CoverageRadius
    vehicle_id: UUID | None = None
    is_active: bool = True


class DeliveryRouteUpdate(BaseModel):
    name: RouteName | None = None
    start_point: GeoPoint | None = None
    end_point: GeoPoint | None = None
    path: RoutePath | None = None
    coverage_radius_m: CoverageRadius | None = None
    vehicle_id: UUID | None = None
    is_active: bool | None = None


class DeliveryRouteVillageRead(BaseReadSchema):
    id: UUID
    name: str


class DeliveryRouteRead(BaseReadSchema):
    id: UUID
    name: str
    village: DeliveryRouteVillageRead
    start_point: GeoPoint
    end_point: GeoPoint
    path: list[GeoPoint] | None
    coverage_radius_m: int
    vehicle: DeliveryVehicleRead | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_route(cls, route: "DeliveryRoute") -> "DeliveryRouteRead":
        return cls(
            id=route.id,
            name=route.name,
            village=DeliveryRouteVillageRead.model_validate(route.village),
            start_point=GeoPoint(latitude=route.start_latitude, longitude=route.start_longitude),
            end_point=GeoPoint(latitude=route.end_latitude, longitude=route.end_longitude),
            path=(
                [GeoPoint(latitude=lat, longitude=lng) for lat, lng in route.path_coordinates]
                if route.path_coordinates is not None
                else None
            ),
            coverage_radius_m=route.coverage_radius_m,
            vehicle=(
                DeliveryVehicleRead.model_validate(route.vehicle)
                if route.vehicle is not None
                else None
            ),
            is_active=route.is_active,
            created_at=route.created_at,
            updated_at=route.updated_at,
        )
