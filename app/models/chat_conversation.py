from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        UniqueConstraint(
            "lower_user_id", "higher_user_id", name="uq_chat_conversations_lower_user_id_higher"
        ),
        CheckConstraint("lower_user_id < higher_user_id", name="ck_chat_conversations_ordered"),
        Index("ix_chat_conversations_higher_user_id", "higher_user_id"),
    )

    lower_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    higher_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    last_message_at: Mapped[datetime | None] = mapped_column(default=None)
