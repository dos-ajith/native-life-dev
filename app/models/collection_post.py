from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class CollectionPost(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "collection_posts"
    __table_args__ = (
        UniqueConstraint(
            "collection_id", "saved_post_id", name="uq_collection_posts_collection_id_saved_post_id"
        ),
        Index("ix_collection_posts_collection_id", "collection_id"),
        Index("ix_collection_posts_saved_post_id", "saved_post_id"),
    )

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    saved_post_id: Mapped[UUID] = mapped_column(ForeignKey("saved_posts.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
