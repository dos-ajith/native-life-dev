from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_ai_settings import UserAISettings


class UserAISettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_user_id(self, user_id: UUID) -> UserAISettings | None:
        return self._db.scalar(
            select(UserAISettings).where(UserAISettings.user_id == user_id)
        )

    def add(self, settings: UserAISettings) -> UserAISettings:
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def save(self, settings: UserAISettings) -> UserAISettings:
        self._db.commit()
        self._db.refresh(settings)
        return settings
