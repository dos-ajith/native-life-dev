from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.base import BaseReadSchema


class NotificationRead(BaseReadSchema):
    id: UUID
    message: str
    is_read: bool
    created_at: datetime


class NotificationUnreadCountRead(BaseModel):
    unread_count: int
