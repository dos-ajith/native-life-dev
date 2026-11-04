from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_vehicle import DeliveryVehicle


class DeliveryVehicleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, vehicle_id: UUID) -> DeliveryVehicle | None:
        return self._db.get(DeliveryVehicle, vehicle_id)

    def list_by_user(self, user_id: UUID) -> list[DeliveryVehicle]:
        stmt = (
            select(DeliveryVehicle)
            .where(DeliveryVehicle.user_id == user_id)
            .order_by(DeliveryVehicle.created_at)
        )
        return list(self._db.scalars(stmt))

    def add(self, vehicle: DeliveryVehicle) -> DeliveryVehicle:
        self._db.add(vehicle)
        self._db.flush()
        return vehicle

    def delete(self, vehicle: DeliveryVehicle) -> None:
        self._db.delete(vehicle)

    def commit(self) -> None:
        self._db.commit()
