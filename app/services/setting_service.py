from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.formatting_context import (
    APP_DATE_FORMAT_SETTING_KEY,
    APP_TIME_FORMAT_SETTING_KEY,
)
from app.core.messages import SettingMessages
from app.core.timezone import APP_TIMEZONE_SETTING_KEY
from app.models.setting import Setting
from app.models.user import User
from app.repositories.setting_repository import SettingRepository
from app.schemas.pagination import PaginationParams
from app.schemas.setting import SettingCreate, SettingUpdate
from app.services.activity_log_service import ActivityLogService
from app.services.app_formatting_service import refresh_datetime_formats
from app.services.app_timezone_service import refresh_app_timezone
from app.services.deal_settings_service import DEAL_SETTING_KEYS, DealSettingsService
from app.services.delivery_access_service import (
    DELIVERY_SETTINGS_ROLES_SETTING_KEY,
    DeliveryAccessService,
)
from app.services.delivery_timeout_service import (
    DELIVERY_TIMEOUT_SETTING_KEYS,
    DeliveryTimeoutService,
)

ENTITY_TYPE = "setting"


class SettingService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = SettingRepository(db)
        self._activity_logs = ActivityLogService(db)

    def create(self, payload: SettingCreate, actor: User) -> Setting:
        if self._settings.get_by_key(payload.key) is not None:
            raise BusinessRuleError(SettingMessages.KEY_TAKEN)
        self._ensure_valid_value(payload.key, payload.value)
        setting = Setting(key=payload.key, value=payload.value)
        saved = self._settings.add(setting)
        self._refresh_caches_if_affected(saved.key)
        self._log(actor, ActivityAction.SETTING_CREATED, saved.id, {"key": saved.key})
        return saved

    def get(self, setting_id: UUID) -> Setting:
        setting = self._settings.get_by_id(setting_id)
        if setting is None:
            raise NotFoundError(SettingMessages.NOT_FOUND)
        return setting

    def get_by_key(self, key: str) -> Setting:
        setting = self._settings.get_by_key(key)
        if setting is None:
            raise NotFoundError(SettingMessages.NOT_FOUND)
        return setting

    def list(self, params: PaginationParams) -> tuple[list[Setting], int]:
        return self._settings.list(params)

    def update(self, setting_id: UUID, payload: SettingUpdate, actor: User) -> Setting:
        setting = self.get(setting_id)
        data: dict[str, Any] = payload.model_dump(exclude_none=True)
        self._check_uniqueness(setting, data)
        self._ensure_valid_value(data.get("key", setting.key), data.get("value", setting.value))
        previous_key = setting.key
        for field, value in data.items():
            setattr(setting, field, value)
        saved = self._settings.save(setting)
        self._refresh_caches_if_affected(previous_key, saved.key)
        self._log(
            actor,
            ActivityAction.SETTING_UPDATED,
            saved.id,
            {"key": saved.key, "previous_key": previous_key, "updated_fields": list(data)},
        )
        return saved

    def delete(self, setting_id: UUID, actor: User) -> None:
        setting = self.get(setting_id)
        key = setting.key
        self._settings.delete(setting)
        self._refresh_caches_if_affected(key)
        self._log(actor, ActivityAction.SETTING_DELETED, setting_id, {"key": key})

    def _ensure_valid_value(self, key: str, value: str | None) -> None:
        if key in DEAL_SETTING_KEYS:
            DealSettingsService(self._db).ensure_valid(key, value)
        elif key == DELIVERY_SETTINGS_ROLES_SETTING_KEY:
            DeliveryAccessService(self._db).ensure_valid(value)
        elif key in DELIVERY_TIMEOUT_SETTING_KEYS:
            DeliveryTimeoutService(self._db).ensure_valid(key, value)

    def _refresh_caches_if_affected(self, *keys: str) -> None:
        if APP_TIMEZONE_SETTING_KEY in keys:
            refresh_app_timezone(self._db)
        if {APP_DATE_FORMAT_SETTING_KEY, APP_TIME_FORMAT_SETTING_KEY} & set(keys):
            refresh_datetime_formats(self._db)

    def _check_uniqueness(self, setting: Setting, data: dict[str, Any]) -> None:
        key = data.get("key")
        if key is not None and key != setting.key and self._settings.get_by_key(key):
            raise BusinessRuleError(SettingMessages.KEY_TAKEN)

    def _log(self, actor: User, action: str, setting_id: UUID, metadata: dict[str, Any]) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=setting_id,
            metadata=metadata,
        )
