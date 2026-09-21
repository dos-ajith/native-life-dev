import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PostMediaType(enum.StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class PostMedia(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "post_media"
    __table_args__ = (Index("ix_post_media_post_id", "post_id"),)

    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    media_type: Mapped[PostMediaType] = mapped_column(
        Enum(
            PostMediaType,
            name="post_media_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    file_url: Mapped[str] = mapped_column(String(2048))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
