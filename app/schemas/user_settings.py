import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.models.user_settings_enums import AIResponseStyle, VisibilityLevel
from app.schemas.base import BaseReadSchema
from app.schemas.geography import GisDistrictRead
from app.schemas.tag import TagRead

_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(-[a-z]{2})?$")


def _validate_language_code(value: str) -> str:
    normalized = value.strip().lower()
    if not _LANGUAGE_CODE_PATTERN.match(normalized):
        raise ValueError("must be a valid language code, e.g. 'en' or 'en-us'")
    return normalized


def _deduplicate_preserving_order(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))


LanguageCode = Annotated[str, AfterValidator(_validate_language_code)]
UniqueIdList = Annotated[list[UUID], AfterValidator(_deduplicate_preserving_order)]


class GeneralSettingsRead(BaseReadSchema):
    id: UUID
    activity_tracking_enabled: bool
    created_at: datetime
    updated_at: datetime


class GeneralSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_tracking_enabled: bool | None = None


class AISettingsRead(BaseReadSchema):
    id: UUID
    ai_enabled: bool
    personalization_enabled: bool
    preferred_language: str
    response_style: AIResponseStyle
    created_at: datetime
    updated_at: datetime


class AISettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_enabled: bool | None = None
    personalization_enabled: bool | None = None
    preferred_language: LanguageCode | None = None
    response_style: AIResponseStyle | None = None


class NotificationSettingsRead(BaseReadSchema):
    id: UUID
    push_enabled: bool
    email_enabled: bool
    post_activity: bool
    comments: bool
    likes: bool
    mentions: bool
    followers: bool
    messages: bool
    ai_updates: bool
    system_updates: bool
    created_at: datetime
    updated_at: datetime


class NotificationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    push_enabled: bool | None = None
    email_enabled: bool | None = None
    post_activity: bool | None = None
    comments: bool | None = None
    likes: bool | None = None
    mentions: bool | None = None
    followers: bool | None = None
    messages: bool | None = None
    ai_updates: bool | None = None
    system_updates: bool | None = None


class PrivacySettingsRead(BaseReadSchema):
    id: UUID
    profile_visibility: VisibilityLevel
    location_visibility: VisibilityLevel
    activity_visibility: VisibilityLevel
    allow_messages: bool
    allow_mentions: bool
    created_at: datetime
    updated_at: datetime


class PrivacySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_visibility: VisibilityLevel | None = None
    location_visibility: VisibilityLevel | None = None
    activity_visibility: VisibilityLevel | None = None
    allow_messages: bool | None = None
    allow_mentions: bool | None = None


class ContentSettingsRead(BaseReadSchema):
    id: UUID
    preferred_categories: list[TagRead]
    preferred_locations: list[GisDistrictRead]
    language_filter: str | None
    hide_sensitive_content: bool
    personalized_feed: bool
    created_at: datetime
    updated_at: datetime


class ContentSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_category_ids: UniqueIdList | None = None
    preferred_location_ids: UniqueIdList | None = None
    language_filter: LanguageCode | None = None
    hide_sensitive_content: bool | None = None
    personalized_feed: bool | None = None


class UserSettingsRead(BaseModel):
    general: GeneralSettingsRead
    ai: AISettingsRead
    notifications: NotificationSettingsRead
    privacy: PrivacySettingsRead
    content: ContentSettingsRead


class UserSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general: GeneralSettingsUpdate | None = None
    ai: AISettingsUpdate | None = None
    notifications: NotificationSettingsUpdate | None = None
    privacy: PrivacySettingsUpdate | None = None
    content: ContentSettingsUpdate | None = None
