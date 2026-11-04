import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class ReactionType(enum.StrEnum):
    LIKE = "like"
    LOVE = "love"
    LAUGH = "laugh"
    WOW = "wow"


class PostLike(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_likes_post_id_user_id"),
        Index("ix_post_likes_post_id", "post_id"),
        Index("ix_post_likes_user_id", "user_id"),
    )

    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reaction_type: Mapped[ReactionType] = mapped_column(
        Enum(
            ReactionType,
            name="post_reaction_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=ReactionType.LIKE,
        server_default=ReactionType.LIKE.value,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
