from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.models.delivery_settings import DeliverySettings
from app.models.user import User
from app.repositories.delivery_settings_repository import (
    DeliverySettingsRepository,
)
from app.schemas.delivery import DeliverySettingsRead, DeliverySettingsUpdate
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "delivery_settings"


class DeliverySettingsService:
    def __init__(self, db: Session) -> None:
        self._settings = DeliverySettingsRepository(db)
        self._activity_logs = ActivityLogService(db)

    def get_mine(self, actor: User) -> DeliverySettingsRead | None:
        settings = self._settings.get_by_user(actor.id)
        return DeliverySettingsRead.from_settings(settings) if settings else None

    def save(self, payload: DeliverySettingsUpdate, actor: User) -> DeliverySettingsRead:
        settings = self._settings.get_by_user(actor.id)
        if settings is None:
            settings = self._settings.add(
                DeliverySettings(user_id=actor.id, **payload.model_dump())
            )
        else:
            for field, value in payload.model_dump().items():
                setattr(settings, field, value)
        self._settings.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_SETTINGS_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=settings.id,
            metadata={
                "working_days": list(settings.working_days),
                "instant_enabled": settings.instant_fee is not None,
                "route_enabled": settings.route_fee is not None,
            },
        )
        return DeliverySettingsRead.from_settings(settings)
