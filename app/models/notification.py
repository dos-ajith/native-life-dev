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
    ROLE_UPGRADE_REQUESTED = "role_upgrade_requested"
    ROLE_UPGRADE_APPROVED = "role_upgrade_approved"
    ROLE_UPGRADE_REJECTED = "role_upgrade_rejected"
    CATEGORY_SUGGESTED = "category_suggested"
    CATEGORY_APPROVED = "category_approved"
    CATEGORY_REJECTED = "category_rejected"
    COMMUNITY_SUBMITTED = "community_submitted"
    COMMUNITY_APPROVED = "community_approved"
    COMMUNITY_REJECTED = "community_rejected"
    COMMUNITY_JOIN_REQUESTED = "community_join_requested"
    COMMUNITY_JOIN_APPROVED = "community_join_approved"
    COMMUNITY_JOIN_REJECTED = "community_join_rejected"
    COMMUNITY_POST_REMOVED = "community_post_removed"
    DEAL_ACCEPTANCE_REQUESTED = "deal_acceptance_requested"
    DEAL_NO_ELIGIBLE_ACCEPTORS = "deal_no_eligible_acceptors"
    DEAL_NO_ELIGIBLE_ACCEPTORS_ADMIN = "deal_no_eligible_acceptors_admin"
    DEAL_PUBLISHED = "deal_published"
    DEAL_EXPIRED = "deal_expired"
    BUSINESS_SUBMITTED = "business_submitted"
    BUSINESS_APPROVED = "business_approved"
    BUSINESS_REJECTED = "business_rejected"
    DELIVERY_REQUESTED = "delivery_requested"
    DELIVERY_ACCEPTED = "delivery_accepted"
    DELIVERY_REJECTED = "delivery_rejected"
    DELIVERY_EXPIRED = "delivery_expired"
    LOST_FOUND_NEARBY = "lost_found_nearby"
    LOST_FOUND_RESOLVED = "lost_found_resolved"
    LOST_FOUND_FOUND = "lost_found_found"
    LOST_FOUND_CLAIMED = "lost_found_claimed"
    LOST_FOUND_CLOSED = "lost_found_closed"


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
