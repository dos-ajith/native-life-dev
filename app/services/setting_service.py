from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import SettingMessages
from app.models.setting import Setting
from app.repositories.setting_repository import SettingRepository
from app.schemas.pagination import PaginationParams
from app.schemas.setting import SettingCreate, SettingUpdate


class SettingService:
    def __init__(self, db: Session) -> None:
        self._settings = SettingRepository(db)

    def create(self, payload: SettingCreate) -> Setting:
        if self._settings.get_by_key(payload.key) is not None:
            raise BusinessRuleError(SettingMessages.KEY_TAKEN)
        setting = Setting(key=payload.key, value=payload.value)
        return self._settings.add(setting)

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

    def update(self, setting_id: UUID, payload: SettingUpdate) -> Setting:
        setting = self.get(setting_id)
        data: dict[str, Any] = payload.model_dump(exclude_none=True)
        self._check_uniqueness(setting, data)
        for field, value in data.items():
            setattr(setting, field, value)
        return self._settings.save(setting)

    def delete(self, setting_id: UUID) -> None:
        setting = self.get(setting_id)
        self._settings.delete(setting)

    def _check_uniqueness(self, setting: Setting, data: dict[str, Any]) -> None:
        key = data.get("key")
        if key is not None and key != setting.key and self._settings.get_by_key(key):
            raise BusinessRuleError(SettingMessages.KEY_TAKEN)
