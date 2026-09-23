from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_privacy_settings import UserPrivacySettings


class UserPrivacySettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_user_id(self, user_id: UUID) -> UserPrivacySettings | None:
        return self._db.scalar(
            select(UserPrivacySettings).where(UserPrivacySettings.user_id == user_id)
        )

    def add(self, settings: UserPrivacySettings) -> UserPrivacySettings:
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def save(self, settings: UserPrivacySettings) -> UserPrivacySettings:
        self._db.commit()
        self._db.refresh(settings)
        return settings
