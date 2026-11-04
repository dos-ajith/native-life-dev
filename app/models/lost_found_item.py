import enum
from datetime import date, datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.category import Category


class LostFoundKind(enum.StrEnum):
    LOST = "lost"
    FOUND = "found"


class LostFoundStatus(enum.StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class LostFoundItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lost_found_items"
    __table_args__ = (
        Index("ix_lost_found_items_user_id", "user_id"),
        Index("ix_lost_found_items_category_id", "category_id"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    kind: Mapped[LostFoundKind] = mapped_column(
        Enum(
            LostFoundKind,
            name="lost_found_kind",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    status: Mapped[LostFoundStatus] = mapped_column(
        Enum(
            LostFoundStatus,
            name="lost_found_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=LostFoundStatus.OPEN,
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text())
    location_name: Mapped[str] = mapped_column(String(500))
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    occurred_on: Mapped[date] = mapped_column(Date())
    contact_info: Mapped[str] = mapped_column(String(150))
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    category: Mapped[Category] = relationship()

    @property
    def latitude(self) -> float:
        return float(to_shape(self.location).y)

    @property
    def longitude(self) -> float:
        return float(to_shape(self.location).x)
