import enum
from datetime import datetime
from typing import Any

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

PLUGIN_KEY_MAX_LENGTH = 30
PLUGIN_VERSION_MAX_LENGTH = 50
SHA256_HEX_LENGTH = 64


class PluginBusinessType(enum.StrEnum):
    PRODUCT = "product"
    SERVICE = "service"


class PluginStatus(enum.StrEnum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"


class Plugin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plugins"

    key: Mapped[str] = mapped_column(String(PLUGIN_KEY_MAX_LENGTH), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    business_type: Mapped[PluginBusinessType] = mapped_column(
        Enum(
            PluginBusinessType,
            name="plugin_business_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    version: Mapped[str] = mapped_column(String(PLUGIN_VERSION_MAX_LENGTH))
    status: Mapped[PluginStatus] = mapped_column(
        Enum(
            PluginStatus,
            name="plugin_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PluginStatus.INSTALLED,
    )
    content_sha256: Mapped[str] = mapped_column(String(SHA256_HEX_LENGTH))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB())
    enabled_at: Mapped[datetime | None] = mapped_column(default=None)
