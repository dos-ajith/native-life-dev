from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_settings_defaults import UserSettingsDefaults
from app.models.user_settings_enums import VisibilityLevel

_visibility_level_type = Enum(
    VisibilityLevel,
    name="visibility_level",
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class UserPrivacySettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_privacy_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    profile_visibility: Mapped[VisibilityLevel] = mapped_column(
        _visibility_level_type, default=UserSettingsDefaults.PROFILE_VISIBILITY
    )
    location_visibility: Mapped[VisibilityLevel] = mapped_column(
        _visibility_level_type, default=UserSettingsDefaults.LOCATION_VISIBILITY
    )
    activity_visibility: Mapped[VisibilityLevel] = mapped_column(
        _visibility_level_type, default=UserSettingsDefaults.ACTIVITY_VISIBILITY
    )
    allow_messages: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.ALLOW_MESSAGES
    )
    allow_mentions: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.ALLOW_MENTIONS
    )
