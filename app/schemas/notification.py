from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.notification import NotificationType
from app.schemas.base import BaseReadSchema


class NotificationRead(BaseReadSchema):
    id: UUID
    type: NotificationType
    message: str
    entity_type: str | None
    entity_id: UUID | None
    is_read: bool
    created_at: datetime


class NotificationUnreadCountRead(BaseModel):
    unread_count: int
