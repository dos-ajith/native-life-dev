import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class NotificationType(enum.StrEnum):
    USER_FOLLOWED = "user_followed"
    FOLLOW_REQUESTED = "follow_requested"
    FOLLOW_REQUEST_ACCEPTED = "follow_request_accepted"
    POST_LIKED = "post_liked"
    POST_COMMENTED = "post_commented"


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_id", "recipient_id"),
        Index(
            "ix_notifications_recipient_id_unread",
            "recipient_id",
            postgresql_where=text("is_read IS FALSE"),
        ),
    )

    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[UUID | None] = mapped_column()
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB())
    is_read: Mapped[bool] = mapped_column(Boolean(), default=False)
    read_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
