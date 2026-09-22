from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_settings_defaults import UserSettingsDefaults
from app.models.user_settings_enums import AIResponseStyle


class UserAISettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_ai_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.AI_ENABLED
    )
    personalization_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=UserSettingsDefaults.PERSONALIZATION_ENABLED
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10), default=UserSettingsDefaults.PREFERRED_LANGUAGE
    )
    response_style: Mapped[AIResponseStyle] = mapped_column(
        Enum(
            AIResponseStyle,
            name="ai_response_style",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserSettingsDefaults.RESPONSE_STYLE,
    )
