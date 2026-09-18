import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PageStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Page(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pages"

    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    content: Mapped[str | None] = mapped_column(Text())
    image_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[PageStatus] = mapped_column(
        Enum(
            PageStatus,
            name="page_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PageStatus.DRAFT,
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(default=None)
