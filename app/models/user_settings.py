from uuid import UUID

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_settings_defaults import UserSettingsDefaults


class UserSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    activity_tracking_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.ACTIVITY_TRACKING_ENABLED
    )
