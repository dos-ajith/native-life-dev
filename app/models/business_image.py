from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BusinessImage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_images"
    __table_args__ = (Index("ix_business_images_business_id", "business_id"),)

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    image_url: Mapped[str] = mapped_column(String(2048))
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
