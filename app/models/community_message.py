from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.user import User


class CommunityMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "community_messages"
    __table_args__ = (
        Index("ix_community_messages_community_id_created_at", "community_id", "created_at"),
        Index("ix_community_messages_reply_to_id", "reply_to_id"),
    )

    community_id: Mapped[UUID] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"))
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reply_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("community_messages.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sender: Mapped[User] = relationship()
    reply_to: Mapped["CommunityMessage | None"] = relationship(
        remote_side="CommunityMessage.id", foreign_keys=[reply_to_id]
    )
