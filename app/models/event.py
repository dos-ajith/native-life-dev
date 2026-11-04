import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.category import Category


class EventStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_id", "user_id"),
        Index("ix_events_category_id", "category_id"),
        Index("ix_events_starts_at", "starts_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text())
    organizer_name: Mapped[str] = mapped_column(String(150))
    organizer_phone: Mapped[str | None] = mapped_column(String(30))
    venue_name: Mapped[str] = mapped_column(String(500))
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[EventStatus] = mapped_column(
        Enum(
            EventStatus,
            name="event_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=EventStatus.SCHEDULED,
    )
    is_featured: Mapped[bool] = mapped_column(Boolean(), default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    category: Mapped[Category] = relationship()

    @property
    def latitude(self) -> float:
        return float(to_shape(self.location).y)

    @property
    def longitude(self) -> float:
        return float(to_shape(self.location).x)
