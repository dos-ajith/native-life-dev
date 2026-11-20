from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import DeliveryVehicleMessages
from app.models.delivery_vehicle import DeliveryVehicle
from app.models.user import User
from app.repositories.delivery_vehicle_repository import DeliveryVehicleRepository
from app.schemas.delivery_vehicle import (
    DeliveryVehicleCreate,
    DeliveryVehicleUpdate,
    TeamVehicleRead,
)
from app.services.activity_log_service import ActivityLogService
from app.services.promoter_team_scope import PromoterTeamScope

ENTITY_TYPE = "delivery_vehicle"


def _full_name(user: User) -> str:
    return f"{user.first_name} {user.last_name}"


class DeliveryVehicleService:
    def __init__(self, db: Session) -> None:
        self._vehicles = DeliveryVehicleRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._team = PromoterTeamScope(db)

    def list_for(self, actor: User) -> list[DeliveryVehicle]:
        return self._vehicles.list_by_user(actor.id)

    def get_owned(self, vehicle_id: UUID, actor: User) -> DeliveryVehicle:
        vehicle = self._vehicles.get_by_id(vehicle_id)
        if vehicle is None or vehicle.user_id != actor.id:
            raise NotFoundError(DeliveryVehicleMessages.NOT_FOUND)
        return vehicle

    def list_for_team(self, promoter: User) -> list[TeamVehicleRead]:
        team = {member.id: member for member in self._team.team(promoter.id)}
        vehicles = self._vehicles.list_by_users(list(team))
        return [
            TeamVehicleRead.model_validate(vehicle).model_copy(
                update={
                    "courier_id": vehicle.user_id,
                    "courier_name": _full_name(team[vehicle.user_id]),
                }
            )
            for vehicle in vehicles
        ]

    def ensure_selectable(self, vehicle_id: UUID, promoter: User) -> None:
        vehicle = self._vehicles.get_by_id(vehicle_id)
        if vehicle is None:
            raise NotFoundError(DeliveryVehicleMessages.NOT_FOUND)
        try:
            self._team.team_member(promoter.id, vehicle.user_id)
        except NotFoundError as error:
            raise NotFoundError(DeliveryVehicleMessages.NOT_FOUND) from error
        if not vehicle.is_active:
            raise BusinessRuleError(DeliveryVehicleMessages.INACTIVE)

    def ensure_belongs_to_courier(self, vehicle_id: UUID, courier_id: UUID) -> None:
        vehicle = self._vehicles.get_by_id(vehicle_id)
        if vehicle is None or vehicle.user_id != courier_id:
            raise BusinessRuleError(DeliveryVehicleMessages.NOT_COURIERS)

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
        if self._vehicles.is_used_by_route(vehicle_id):
            raise ConflictError(DeliveryVehicleMessages.IN_USE)
        self._vehicles.delete(vehicle)
        self._vehicles.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_VEHICLE_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=vehicle_id,
        )
