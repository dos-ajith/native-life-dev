from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.delivery_vehicle import VEHICLE_NAME_LENGTH, VehicleType
from app.schemas.base import BaseReadSchema
from app.schemas.validators import NonBlankStr

VehicleName = Annotated[NonBlankStr, Field(max_length=VEHICLE_NAME_LENGTH)]


class DeliveryVehicleCreate(BaseModel):
    vehicle_type: VehicleType
    name: VehicleName
    is_active: bool = True


class DeliveryVehicleUpdate(BaseModel):
    vehicle_type: VehicleType | None = None
    name: VehicleName | None = None
    is_active: bool | None = None


class DeliveryVehicleRead(BaseReadSchema):
    id: UUID
    vehicle_type: VehicleType
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
