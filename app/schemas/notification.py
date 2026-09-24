from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from app.models.notification import NotificationType
from app.schemas.base import BaseReadSchema
from app.schemas.user import UserSummaryRead

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.user import User


class NotificationTargetRead(BaseModel):
    type: str
    id: UUID


class NotificationRead(BaseReadSchema):
    id: UUID
    type: NotificationType
    actor: UserSummaryRead | None
    target: NotificationTargetRead | None
    metadata: dict[str, Any] | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_notification(
        cls,
        notification: "Notification",
        actor: "User | None",
        target: NotificationTargetRead | None,
    ) -> "NotificationRead":
        return cls(
            id=notification.id,
            type=notification.type,
            actor=UserSummaryRead.model_validate(actor) if actor is not None else None,
            target=target,
            metadata=notification.metadata_,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )


class NotificationUnreadCountRead(BaseModel):
    unread_count: int
