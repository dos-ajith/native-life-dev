import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.plugin import PLUGIN_KEY_MAX_LENGTH, PLUGIN_VERSION_MAX_LENGTH, SHA256_HEX_LENGTH


class PluginInstallationAction(enum.StrEnum):
    INSTALL = "install"
    UPGRADE = "upgrade"
    REAPPLY = "reapply"
    DOWNGRADE = "downgrade"


class PluginInstallationStatus(enum.StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PluginInstallation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plugin_installations"

    plugin_key: Mapped[str] = mapped_column(String(PLUGIN_KEY_MAX_LENGTH))
    plugin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("plugins.id", ondelete="SET NULL"), default=None
    )
    action: Mapped[PluginInstallationAction] = mapped_column(
        Enum(
            PluginInstallationAction,
            name="plugin_installation_action",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    status: Mapped[PluginInstallationStatus] = mapped_column(
        Enum(
            PluginInstallationStatus,
            name="plugin_installation_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    from_version: Mapped[str | None] = mapped_column(String(PLUGIN_VERSION_MAX_LENGTH))
    to_version: Mapped[str] = mapped_column(String(PLUGIN_VERSION_MAX_LENGTH))
    content_sha256: Mapped[str] = mapped_column(String(SHA256_HEX_LENGTH))
    error: Mapped[str | None] = mapped_column(Text())
