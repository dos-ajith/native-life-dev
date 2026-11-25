from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PostCommentLike(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "post_comment_likes"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_post_comment_likes_comment_id_user_id"),
    )

    comment_id: Mapped[UUID] = mapped_column(ForeignKey("post_comments.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
