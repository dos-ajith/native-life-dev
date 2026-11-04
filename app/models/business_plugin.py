import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BusinessPluginStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class BusinessPlugin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_plugins"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "plugin_id", name="uq_business_plugins_business_id_plugin_id"
        ),
    )

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    plugin_id: Mapped[UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"))
    status: Mapped[BusinessPluginStatus] = mapped_column(
        Enum(
            BusinessPluginStatus,
            name="business_plugin_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    enabled_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
