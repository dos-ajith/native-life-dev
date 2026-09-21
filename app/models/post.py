import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PostStatus(enum.StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"


class Post(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_user_id", "user_id"),
        Index("ix_posts_status", "status"),
        Index("ix_posts_deleted_at", "deleted_at"),
        Index("ix_posts_published_by", "published_by"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text())
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            name="post_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PostStatus.DRAFT,
    )
    location: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    location_name: Mapped[str | None] = mapped_column(String(500))
    scheduled_at: Mapped[datetime | None] = mapped_column(default=None)
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    published_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    likes_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    comments_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    shares_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def latitude(self) -> float | None:
        return to_shape(self.location).y if self.location is not None else None

    @property
    def longitude(self) -> float | None:
        return to_shape(self.location).x if self.location is not None else None
