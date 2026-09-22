from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.gis_district import GisDistrict
from app.models.tag import Tag
from app.models.user_content_preferred_district import user_content_preferred_districts
from app.models.user_content_preferred_tag import user_content_preferred_tags
from app.models.user_content_settings import UserContentSettings


class UserContentSettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_user_id(self, user_id: UUID) -> UserContentSettings | None:
        return self._db.scalar(
            select(UserContentSettings).where(UserContentSettings.user_id == user_id)
        )

    def add(self, settings: UserContentSettings) -> UserContentSettings:
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def save(self, settings: UserContentSettings) -> UserContentSettings:
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def list_preferred_tags(self, content_settings_id: UUID) -> list[Tag]:
        return list(
            self._db.scalars(
                select(Tag)
                .join(
                    user_content_preferred_tags,
                    user_content_preferred_tags.c.tag_id == Tag.id,
                )
                .where(
                    user_content_preferred_tags.c.user_content_settings_id == content_settings_id
                )
                .order_by(Tag.name)
            )
        )

    def replace_preferred_tags(self, content_settings_id: UUID, tag_ids: list[UUID]) -> None:
        self._db.execute(
            delete(user_content_preferred_tags).where(
                user_content_preferred_tags.c.user_content_settings_id == content_settings_id
            )
        )
        if tag_ids:
            self._db.execute(
                insert(user_content_preferred_tags),
                [
                    {"user_content_settings_id": content_settings_id, "tag_id": tag_id}
                    for tag_id in tag_ids
                ],
            )
        self._db.commit()

    def list_preferred_districts(self, content_settings_id: UUID) -> list[GisDistrict]:
        return list(
            self._db.scalars(
                select(GisDistrict)
                .join(
                    user_content_preferred_districts,
                    user_content_preferred_districts.c.district_id == GisDistrict.id,
                )
                .where(
                    user_content_preferred_districts.c.user_content_settings_id
                    == content_settings_id
                )
                .order_by(GisDistrict.name)
            )
        )

    def replace_preferred_districts(
        self, content_settings_id: UUID, district_ids: list[UUID]
    ) -> None:
        self._db.execute(
            delete(user_content_preferred_districts).where(
                user_content_preferred_districts.c.user_content_settings_id
                == content_settings_id
            )
        )
        if district_ids:
            self._db.execute(
                insert(user_content_preferred_districts),
                [
                    {"user_content_settings_id": content_settings_id, "district_id": district_id}
                    for district_id in district_ids
                ],
            )
        self._db.commit()
