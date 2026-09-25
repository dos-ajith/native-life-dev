from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class SavedPost(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "saved_posts"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_saved_posts_user_id_post_id"),
        Index("ix_saved_posts_user_id", "user_id"),
        Index("ix_saved_posts_post_id", "post_id"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
