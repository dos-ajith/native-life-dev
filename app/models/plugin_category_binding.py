import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PluginCategoryOwnership(enum.StrEnum):
    CREATED = "created"
    ADOPTED = "adopted"


class PluginCategoryBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plugin_category_bindings"
    __table_args__ = (
        UniqueConstraint(
            "plugin_id", "category_id", name="uq_plugin_category_bindings_plugin_id_category_id"
        ),
        Index("ix_plugin_category_bindings_category_id", "category_id"),
    )

    plugin_id: Mapped[UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    ownership: Mapped[PluginCategoryOwnership] = mapped_column(
        Enum(
            PluginCategoryOwnership,
            name="plugin_category_ownership",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    applies_to_businesses: Mapped[bool] = mapped_column(
        Boolean(), server_default=text("false"), default=False
    )
    include_descendants: Mapped[bool] = mapped_column(
        Boolean(), server_default=text("false"), default=False
    )
    removed_at: Mapped[datetime | None] = mapped_column(default=None)
