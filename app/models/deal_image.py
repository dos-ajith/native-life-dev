from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DealImage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deal_images"
    __table_args__ = (
        Index("ix_deal_images_deal_id", "deal_id"),
        Index(
            "uq_deal_images_one_thumbnail",
            "deal_id",
            unique=True,
            postgresql_where=text("is_thumbnail"),
        ),
    )

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    storage_path: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer())
    is_thumbnail: Mapped[bool] = mapped_column(Boolean(), default=False)
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
