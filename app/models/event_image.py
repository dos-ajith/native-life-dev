from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EventImage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_images"
    __table_args__ = (Index("ix_event_images_event_id", "event_id"),)

    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    image_url: Mapped[str] = mapped_column(String(2048))
    caption: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
