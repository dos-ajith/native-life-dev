from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import NotFoundError
from app.core.messages import DeliveryVehicleMessages
from app.models.delivery_vehicle import DeliveryVehicle
from app.models.user import User
from app.repositories.delivery_vehicle_repository import DeliveryVehicleRepository
from app.schemas.delivery_vehicle import DeliveryVehicleCreate, DeliveryVehicleUpdate
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "delivery_vehicle"


class DeliveryVehicleService:
    def __init__(self, db: Session) -> None:
        self._vehicles = DeliveryVehicleRepository(db)
        self._activity_logs = ActivityLogService(db)

    def list_for(self, actor: User) -> list[DeliveryVehicle]:
        return self._vehicles.list_by_user(actor.id)

    def get_owned(self, vehicle_id: UUID, actor: User) -> DeliveryVehicle:
        vehicle = self._vehicles.get_by_id(vehicle_id)
        if vehicle is None or vehicle.user_id != actor.id:
            raise NotFoundError(DeliveryVehicleMessages.NOT_FOUND)
        return vehicle

    def create(self, payload: DeliveryVehicleCreate, actor: User) -> DeliveryVehicle:
        vehicle = self._vehicles.add(DeliveryVehicle(user_id=actor.id, **payload.model_dump()))
        self._vehicles.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_VEHICLE_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=vehicle.id,
            metadata={"vehicle_type": vehicle.vehicle_type.value},
        )
        return vehicle

    def update(
        self, vehicle_id: UUID, payload: DeliveryVehicleUpdate, actor: User
    ) -> DeliveryVehicle:
        vehicle = self.get_owned(vehicle_id, actor)
        changes = payload.model_dump(exclude_none=True)
        for field, value in changes.items():
            setattr(vehicle, field, value)
        self._vehicles.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_VEHICLE_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=vehicle_id,
            metadata={"updated_fields": list(changes.keys())},
        )
        return vehicle

    def delete(self, vehicle_id: UUID, actor: User) -> None:
        vehicle = self.get_owned(vehicle_id, actor)
        self._vehicles.delete(vehicle)
        self._vehicles.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_VEHICLE_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=vehicle_id,
        )
