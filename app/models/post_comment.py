from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PostComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "post_comments"
    __table_args__ = (
        Index("ix_post_comments_post_id", "post_id"),
        Index("ix_post_comments_user_id", "user_id"),
        Index("ix_post_comments_parent_id", "parent_id"),
    )

    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("post_comments.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text())
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
