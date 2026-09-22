from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_settings_defaults import UserSettingsDefaults


class UserContentSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_content_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    language_filter: Mapped[str | None] = mapped_column(String(10))
    hide_sensitive_content: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.HIDE_SENSITIVE_CONTENT
    )
    personalized_feed: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.PERSONALIZED_FEED
    )
