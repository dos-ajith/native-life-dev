import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class DirectMessageMediaType(enum.StrEnum):
    IMAGE = "image"
    VIDEO = "video"


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
    media_type: Mapped[DirectMessageMediaType | None] = mapped_column(
        Enum(
            DirectMessageMediaType,
            name="direct_message_media_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=None,
    )
    media_storage_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    media_content_type: Mapped[str | None] = mapped_column(String(100), default=None)
    media_size_bytes: Mapped[int | None] = mapped_column(Integer(), default=None)
    read_at: Mapped[datetime | None] = mapped_column(default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
