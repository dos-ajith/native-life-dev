from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class UserFollow(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint(
            "follower_id", "following_id", name="uq_user_follows_follower_id_following_id"
        ),
        CheckConstraint("follower_id <> following_id", name="ck_user_follows_not_self"),
        Index("ix_user_follows_following_id", "following_id"),
    )

    follower_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    following_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
