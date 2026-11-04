from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import DbSessionDep
from app.api.v1.deals.permissions import DeliverySettingsManagerDep
from app.core.messages import DeliveryVehicleMessages
from app.core.openapi_tags import ApiTag
from app.schemas.delivery_vehicle import (
    DeliveryVehicleCreate,
    DeliveryVehicleRead,
    DeliveryVehicleUpdate,
)
from app.schemas.response import SuccessResponse
from app.services.delivery_vehicle_service import DeliveryVehicleService

router = APIRouter(prefix="/me/delivery-vehicles", tags=[ApiTag.DELIVERY_VEHICLES])


@router.get("", response_model=SuccessResponse[list[DeliveryVehicleRead]])
def list_my_vehicles(
    db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[list[DeliveryVehicleRead]]:
    vehicles = DeliveryVehicleService(db).list_for(current_user)
    return SuccessResponse(
        message=DeliveryVehicleMessages.LIST_RETRIEVED,
        data=[DeliveryVehicleRead.model_validate(vehicle) for vehicle in vehicles],
    )


@router.post(
    "", response_model=SuccessResponse[DeliveryVehicleRead], status_code=status.HTTP_201_CREATED
)
def create_my_vehicle(
    payload: DeliveryVehicleCreate, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[DeliveryVehicleRead]:
    vehicle = DeliveryVehicleService(db).create(payload, current_user)
    return SuccessResponse(
        message=DeliveryVehicleMessages.CREATED, data=DeliveryVehicleRead.model_validate(vehicle)
    )


@router.get("/{vehicle_id}", response_model=SuccessResponse[DeliveryVehicleRead])
def get_my_vehicle(
    vehicle_id: UUID, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[DeliveryVehicleRead]:
    vehicle = DeliveryVehicleService(db).get_owned(vehicle_id, current_user)
    return SuccessResponse(
        message=DeliveryVehicleMessages.RETRIEVED, data=DeliveryVehicleRead.model_validate(vehicle)
    )


@router.patch("/{vehicle_id}", response_model=SuccessResponse[DeliveryVehicleRead])
def update_my_vehicle(
    vehicle_id: UUID,
    payload: DeliveryVehicleUpdate,
    db: DbSessionDep,
    current_user: DeliverySettingsManagerDep,
) -> SuccessResponse[DeliveryVehicleRead]:
    vehicle = DeliveryVehicleService(db).update(vehicle_id, payload, current_user)
    return SuccessResponse(
        message=DeliveryVehicleMessages.UPDATED, data=DeliveryVehicleRead.model_validate(vehicle)
    )


@router.delete("/{vehicle_id}", response_model=SuccessResponse[None])
def delete_my_vehicle(
    vehicle_id: UUID, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[None]:
    DeliveryVehicleService(db).delete(vehicle_id, current_user)
    return SuccessResponse(message=DeliveryVehicleMessages.DELETED, data=None)
