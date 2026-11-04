from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LostFoundImage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lost_found_images"
    __table_args__ = (Index("ix_lost_found_images_item_id", "item_id"),)

    item_id: Mapped[UUID] = mapped_column(ForeignKey("lost_found_items.id", ondelete="CASCADE"))
    image_url: Mapped[str] = mapped_column(String(2048))
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
