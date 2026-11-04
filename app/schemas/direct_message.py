from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.direct_message import DirectMessage
from app.schemas.base import BaseReadSchema
from app.schemas.community_message import MessageContent
from app.schemas.presence import PresenceRead
from app.schemas.user import UserSummaryRead


class DirectMessageCreate(BaseModel):
    content: MessageContent


class DirectMessageRead(BaseReadSchema):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_message(cls, message: DirectMessage) -> "DirectMessageRead":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            content=message.content,
            read_at=message.read_at,
            created_at=message.created_at,
        )


class DirectMessageHistory(BaseModel):
    items: list[DirectMessageRead]
    has_more: bool
    next_before_id: UUID | None


class ConversationRead(BaseModel):
    id: UUID
    user: UserSummaryRead
    last_message: DirectMessageRead | None
    unread_count: int
    blocked_by_me: bool
    presence: PresenceRead
