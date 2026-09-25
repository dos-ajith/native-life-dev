from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class UserFollowRequest(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_follow_requests"
    __table_args__ = (
        UniqueConstraint(
            "requester_id", "target_id", name="uq_user_follow_requests_requester_id_target_id"
        ),
        CheckConstraint("requester_id <> target_id", name="ck_user_follow_requests_not_self"),
        Index("ix_user_follow_requests_target_id", "target_id"),
    )

    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
