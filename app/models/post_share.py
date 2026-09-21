from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class PostShare(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "post_shares"
    __table_args__ = (
        Index("ix_post_shares_post_id", "post_id"),
        Index("ix_post_shares_user_id", "user_id"),
    )

    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
