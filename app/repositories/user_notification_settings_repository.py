from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_notification_settings import UserNotificationSettings


class UserNotificationSettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_user_id(self, user_id: UUID) -> UserNotificationSettings | None:
        return self._db.scalar(
            select(UserNotificationSettings).where(UserNotificationSettings.user_id == user_id)
        )

    def add(self, settings: UserNotificationSettings) -> UserNotificationSettings:
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def save(self, settings: UserNotificationSettings) -> UserNotificationSettings:
        self._db.commit()
        self._db.refresh(settings)
        return settings
