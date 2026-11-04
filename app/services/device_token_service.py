from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.models.device_token import DeviceToken
from app.models.user import User
from app.repositories.device_token_repository import DeviceTokenRepository
from app.schemas.device_token import DeviceTokenRegister
from app.services.activity_log_service import ActivityLogService

DEVICE_TOKEN_ENTITY_TYPE = "device_token"
PLATFORM_METADATA_KEY = "platform"


class DeviceTokenService:
    def __init__(self, db: Session) -> None:
        self._devices = DeviceTokenRepository(db)
        self._activity_logs = ActivityLogService(db)

    def register(self, actor: User, payload: DeviceTokenRegister) -> DeviceToken:
        existing = self._devices.get_by_token(payload.token)
        if (
            existing is not None
            and existing.user_id == actor.id
            and existing.platform == payload.platform
        ):
            return existing
        device = self._devices.upsert(actor.id, payload.token, payload.platform)
        self._activity_logs.log(
            actor,
            ActivityAction.DEVICE_REGISTERED,
            entity_type=DEVICE_TOKEN_ENTITY_TYPE,
            entity_id=device.id,
            metadata={PLATFORM_METADATA_KEY: payload.platform.value},
        )
        return device

    def remove(self, actor: User, token: str) -> None:
        device = self._devices.delete_for_user(actor.id, token)
        if device is None:
            return
        self._activity_logs.log(
            actor,
            ActivityAction.DEVICE_REMOVED,
            entity_type=DEVICE_TOKEN_ENTITY_TYPE,
            entity_id=device.id,
            metadata={PLATFORM_METADATA_KEY: device.platform.value},
        )
