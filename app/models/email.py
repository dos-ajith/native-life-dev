import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailType(enum.StrEnum):
    EMAIL_VERIFICATION = "email_verification"


class EmailStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"


class Email(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "emails"
    __table_args__ = (
        Index("ix_emails_provider_message_id", "provider_message_id", unique=True),
        Index("ix_emails_status", "status"),
        Index("ix_emails_email_type", "email_type"),
        Index("ix_emails_created_at", "created_at"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    to_email: Mapped[str] = mapped_column(String(255))
    from_email: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    text_body: Mapped[str] = mapped_column(Text())
    html_body: Mapped[str] = mapped_column(Text())
    email_type: Mapped[EmailType] = mapped_column(
        Enum(
            EmailType,
            name="email_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    provider: Mapped[str] = mapped_column(String(50))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[EmailStatus] = mapped_column(
        Enum(
            EmailStatus,
            name="email_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=EmailStatus.PENDING,
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text())
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB())
    sent_at: Mapped[datetime | None] = mapped_column(default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(default=None)
    failed_at: Mapped[datetime | None] = mapped_column(default=None)
