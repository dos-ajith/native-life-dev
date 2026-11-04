import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

DEVICE_TOKEN_MAX_LENGTH = 1024


class DevicePlatform(enum.StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class DeviceToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "device_tokens"
    __table_args__ = (Index("ix_device_tokens_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(DEVICE_TOKEN_MAX_LENGTH), unique=True)
    platform: Mapped[DevicePlatform] = mapped_column(
        Enum(
            DevicePlatform,
            name="device_platform",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
