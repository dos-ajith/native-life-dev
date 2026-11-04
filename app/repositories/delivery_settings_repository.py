from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_settings import DeliverySettings


class DeliverySettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_user(self, user_id: UUID) -> DeliverySettings | None:
        return self._db.scalar(select(DeliverySettings).where(DeliverySettings.user_id == user_id))

    def add(self, settings: DeliverySettings) -> DeliverySettings:
        self._db.add(settings)
        self._db.flush()
        return settings

    def commit(self) -> None:
        self._db.commit()
