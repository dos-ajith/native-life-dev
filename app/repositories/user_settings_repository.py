from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_settings import UserSettings


class UserSettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        return self._db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))

    def add(self, settings: UserSettings) -> UserSettings:
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def save(self, settings: UserSettings) -> UserSettings:
        self._db.commit()
        self._db.refresh(settings)
        return settings
