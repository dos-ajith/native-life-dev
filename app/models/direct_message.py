from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class DirectMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "direct_messages"
    __table_args__ = (
        Index("ix_direct_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE")
    )
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text())
    read_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
