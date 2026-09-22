from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError
from app.core.messages import UserSettingsMessages
from app.models.user import User
from app.models.user_ai_settings import UserAISettings
from app.models.user_content_settings import UserContentSettings
from app.models.user_notification_settings import UserNotificationSettings
from app.models.user_privacy_settings import UserPrivacySettings
from app.models.user_settings import UserSettings
from app.repositories.gis_district_repository import GisDistrictRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.user_ai_settings_repository import UserAISettingsRepository
from app.repositories.user_content_settings_repository import UserContentSettingsRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.repositories.user_privacy_settings_repository import UserPrivacySettingsRepository
from app.repositories.user_settings_repository import UserSettingsRepository
from app.schemas.geography import GisDistrictRead
from app.schemas.tag import TagRead
from app.schemas.user_settings import (
    AISettingsRead,
    AISettingsUpdate,
    ContentSettingsRead,
    ContentSettingsUpdate,
    GeneralSettingsRead,
    GeneralSettingsUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    PrivacySettingsRead,
    PrivacySettingsUpdate,
    UserSettingsRead,
    UserSettingsUpdate,
)
from app.services.activity_log_service import ActivityLogService


class UserSettingsService:
    def __init__(self, db: Session) -> None:
        self._settings = UserSettingsRepository(db)
        self._ai_settings = UserAISettingsRepository(db)
        self._notification_settings = UserNotificationSettingsRepository(db)
        self._privacy_settings = UserPrivacySettingsRepository(db)
        self._content_settings = UserContentSettingsRepository(db)
        self._tags = TagRepository(db)
        self._districts = GisDistrictRepository(db)
        self._activity_logs = ActivityLogService(db)

    def _get_or_create_general(self, user: User) -> UserSettings:
        settings = self._settings.get_by_user_id(user.id)
        if settings is not None:
            return settings
        return self._settings.add(UserSettings(user_id=user.id))

    def _get_or_create_ai(self, user: User) -> UserAISettings:
        settings = self._ai_settings.get_by_user_id(user.id)
        if settings is not None:
            return settings
        return self._ai_settings.add(UserAISettings(user_id=user.id))

    def _get_or_create_notifications(self, user: User) -> UserNotificationSettings:
        settings = self._notification_settings.get_by_user_id(user.id)
        if settings is not None:
            return settings
        return self._notification_settings.add(UserNotificationSettings(user_id=user.id))

    def _get_or_create_privacy(self, user: User) -> UserPrivacySettings:
        settings = self._privacy_settings.get_by_user_id(user.id)
        if settings is not None:
            return settings
        return self._privacy_settings.add(UserPrivacySettings(user_id=user.id))

    def _get_or_create_content(self, user: User) -> UserContentSettings:
        settings = self._content_settings.get_by_user_id(user.id)
        if settings is not None:
            return settings
        return self._content_settings.add(UserContentSettings(user_id=user.id))

    def get_general(self, user: User) -> GeneralSettingsRead:
        return GeneralSettingsRead.model_validate(self._get_or_create_general(user))

    def get_ai(self, user: User) -> AISettingsRead:
        return AISettingsRead.model_validate(self._get_or_create_ai(user))

    def get_notifications(self, user: User) -> NotificationSettingsRead:
        return NotificationSettingsRead.model_validate(self._get_or_create_notifications(user))

    def get_privacy(self, user: User) -> PrivacySettingsRead:
        return PrivacySettingsRead.model_validate(self._get_or_create_privacy(user))

    def get_content(self, user: User) -> ContentSettingsRead:
        return self._to_content_read(self._get_or_create_content(user))

    def get_aggregate(self, user: User) -> UserSettingsRead:
        return UserSettingsRead(
            general=self.get_general(user),
            ai=self.get_ai(user),
            notifications=self.get_notifications(user),
            privacy=self.get_privacy(user),
            content=self.get_content(user),
        )

    def update_general(self, user: User, payload: GeneralSettingsUpdate) -> GeneralSettingsRead:
        settings = self._get_or_create_general(user)
        data = payload.model_dump(exclude_none=True)
        for field, value in data.items():
            setattr(settings, field, value)
        saved = self._settings.save(settings)
        if data:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.USER_GENERAL_SETTINGS_UPDATED,
                entity_type="user_settings",
                entity_id=saved.id,
                metadata={"changed_fields": list(data.keys())},
            )
        return GeneralSettingsRead.model_validate(saved)

    def update_ai(self, user: User, payload: AISettingsUpdate) -> AISettingsRead:
        settings = self._get_or_create_ai(user)
        data = payload.model_dump(exclude_none=True)
        for field, value in data.items():
            setattr(settings, field, value)
        saved = self._ai_settings.save(settings)
        if data:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.USER_AI_SETTINGS_UPDATED,
                entity_type="user_ai_settings",
                entity_id=saved.id,
                metadata={"changed_fields": list(data.keys())},
            )
        return AISettingsRead.model_validate(saved)

    def update_notifications(
        self, user: User, payload: NotificationSettingsUpdate
    ) -> NotificationSettingsRead:
        settings = self._get_or_create_notifications(user)
        data = payload.model_dump(exclude_none=True)
        for field, value in data.items():
            setattr(settings, field, value)
        saved = self._notification_settings.save(settings)
        if data:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.USER_NOTIFICATION_SETTINGS_UPDATED,
                entity_type="user_notification_settings",
                entity_id=saved.id,
                metadata={"changed_fields": list(data.keys())},
            )
        return NotificationSettingsRead.model_validate(saved)

    def update_privacy(self, user: User, payload: PrivacySettingsUpdate) -> PrivacySettingsRead:
        settings = self._get_or_create_privacy(user)
        data = payload.model_dump(exclude_none=True)
        for field, value in data.items():
            setattr(settings, field, value)
        saved = self._privacy_settings.save(settings)
        if data:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.USER_PRIVACY_SETTINGS_UPDATED,
                entity_type="user_privacy_settings",
                entity_id=saved.id,
                metadata={"changed_fields": list(data.keys())},
            )
        return PrivacySettingsRead.model_validate(saved)

    def update_content(self, user: User, payload: ContentSettingsUpdate) -> ContentSettingsRead:
        if payload.preferred_category_ids is not None:
            self._validate_tag_ids(payload.preferred_category_ids)
        if payload.preferred_location_ids is not None:
            self._validate_district_ids(payload.preferred_location_ids)

        settings = self._get_or_create_content(user)
        data = payload.model_dump(
            exclude_none=True, exclude={"preferred_category_ids", "preferred_location_ids"}
        )
        for field, value in data.items():
            setattr(settings, field, value)
        saved = self._content_settings.save(settings)

        changed_fields = list(data.keys())
        if payload.preferred_category_ids is not None:
            self._content_settings.replace_preferred_tags(
                saved.id, payload.preferred_category_ids
            )
            changed_fields.append("preferred_category_ids")
        if payload.preferred_location_ids is not None:
            self._content_settings.replace_preferred_districts(
                saved.id, payload.preferred_location_ids
            )
            changed_fields.append("preferred_location_ids")

        if changed_fields:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.USER_CONTENT_SETTINGS_UPDATED,
                entity_type="user_content_settings",
                entity_id=saved.id,
                metadata={"changed_fields": changed_fields},
            )
        return self._to_content_read(saved)

    def update_aggregate(self, user: User, payload: UserSettingsUpdate) -> UserSettingsRead:
        if payload.content is not None:
            if payload.content.preferred_category_ids is not None:
                self._validate_tag_ids(payload.content.preferred_category_ids)
            if payload.content.preferred_location_ids is not None:
                self._validate_district_ids(payload.content.preferred_location_ids)

        changed_sections: dict[str, list[str]] = {}

        if payload.general is not None:
            data = payload.general.model_dump(exclude_none=True)
            if data:
                changed_sections["general"] = list(data.keys())
            self.update_general(user, payload.general)
        if payload.ai is not None:
            data = payload.ai.model_dump(exclude_none=True)
            if data:
                changed_sections["ai"] = list(data.keys())
            self.update_ai(user, payload.ai)
        if payload.notifications is not None:
            data = payload.notifications.model_dump(exclude_none=True)
            if data:
                changed_sections["notifications"] = list(data.keys())
            self.update_notifications(user, payload.notifications)
        if payload.privacy is not None:
            data = payload.privacy.model_dump(exclude_none=True)
            if data:
                changed_sections["privacy"] = list(data.keys())
            self.update_privacy(user, payload.privacy)
        if payload.content is not None:
            data = payload.content.model_dump(exclude_none=True)
            if data:
                changed_sections["content"] = list(data.keys())
            self.update_content(user, payload.content)

        if changed_sections:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.USER_SETTINGS_UPDATED,
                entity_type="user",
                entity_id=user.id,
                metadata={"changed_sections": changed_sections},
            )
        return self.get_aggregate(user)

    def _validate_tag_ids(self, tag_ids: list[UUID]) -> None:
        tags = self._tags.get_by_ids(tag_ids)
        missing_ids = set(tag_ids) - {tag.id for tag in tags}
        if missing_ids:
            ids = ", ".join(str(tag_id) for tag_id in missing_ids)
            raise BusinessRuleError(UserSettingsMessages.UNKNOWN_TAG_IDS.format(ids=ids))

    def _validate_district_ids(self, district_ids: list[UUID]) -> None:
        districts = self._districts.get_by_ids(district_ids)
        missing_ids = set(district_ids) - {district.id for district in districts}
        if missing_ids:
            ids = ", ".join(str(district_id) for district_id in missing_ids)
            raise BusinessRuleError(UserSettingsMessages.UNKNOWN_DISTRICT_IDS.format(ids=ids))

    def _to_content_read(self, settings: UserContentSettings) -> ContentSettingsRead:
        tags = self._content_settings.list_preferred_tags(settings.id)
        districts = self._content_settings.list_preferred_districts(settings.id)
        return ContentSettingsRead(
            id=settings.id,
            preferred_categories=[TagRead.model_validate(tag) for tag in tags],
            preferred_locations=[GisDistrictRead.model_validate(d) for d in districts],
            language_filter=settings.language_filter,
            hide_sensitive_content=settings.hide_sensitive_content,
            personalized_feed=settings.personalized_feed,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )
