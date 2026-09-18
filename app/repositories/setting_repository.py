from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.setting import Setting
from app.schemas.pagination import PaginationParams


class SettingRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, setting_id: UUID) -> Setting | None:
        return self._db.get(Setting, setting_id)

    def get_by_key(self, key: str) -> Setting | None:
        return self._db.scalar(select(Setting).where(Setting.key == key))

    def list(self, params: PaginationParams) -> tuple[list[Setting], int]:
        total = self._db.scalar(select(func.count()).select_from(Setting)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Setting)
            .order_by(Setting.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, setting: Setting) -> Setting:
        self._db.add(setting)
        self._db.commit()
        self._db.refresh(setting)
        return setting

    def save(self, setting: Setting) -> Setting:
        self._db.commit()
        self._db.refresh(setting)
        return setting

    def delete(self, setting: Setting) -> None:
        self._db.delete(setting)
        self._db.commit()
