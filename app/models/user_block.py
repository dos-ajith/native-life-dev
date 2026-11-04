from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class UserBlock(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_id_blocked_id"),
        CheckConstraint("blocker_id <> blocked_id", name="ck_user_blocks_not_self"),
    )

    blocker_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    blocked_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
