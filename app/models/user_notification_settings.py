from uuid import UUID

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_settings_defaults import UserSettingsDefaults


class UserNotificationSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_notification_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    push_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.PUSH_ENABLED
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.EMAIL_ENABLED
    )
    post_activity: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.POST_ACTIVITY
    )
    comments: Mapped[bool] = mapped_column(Boolean(), default=UserSettingsDefaults.COMMENTS)
    likes: Mapped[bool] = mapped_column(Boolean(), default=UserSettingsDefaults.LIKES)
    mentions: Mapped[bool] = mapped_column(Boolean(), default=UserSettingsDefaults.MENTIONS)
    followers: Mapped[bool] = mapped_column(Boolean(), default=UserSettingsDefaults.FOLLOWERS)
    messages: Mapped[bool] = mapped_column(Boolean(), default=UserSettingsDefaults.MESSAGES)
    ai_updates: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.AI_UPDATES
    )
    system_updates: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.SYSTEM_UPDATES
    )
