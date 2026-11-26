import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.config import get_settings
from app.models.direct_message import DirectMessage, DirectMessageMediaType
from app.schemas.base import BaseReadSchema
from app.schemas.community_message import MessageContent
from app.schemas.presence import PresenceRead
from app.schemas.user import UserSummaryRead


class DirectMessageCreate(BaseModel):
    content: MessageContent


class DeleteScope(enum.StrEnum):
    ME = "me"
    EVERYONE = "everyone"


def direct_message_media_url(message_id: UUID) -> str:
    return f"{get_settings().api_v1_prefix}/chats/messages/{message_id}/media"


class DirectMessageMediaRead(BaseModel):
    type: DirectMessageMediaType
    content_type: str
    size_bytes: int
    url: str

    @classmethod
    def from_message(cls, message: DirectMessage) -> "DirectMessageMediaRead | None":
        if (
            message.media_type is None
            or message.media_content_type is None
            or message.media_size_bytes is None
        ):
            return None
        return cls(
            type=message.media_type,
            content_type=message.media_content_type,
            size_bytes=message.media_size_bytes,
            url=direct_message_media_url(message.id),
        )


class DirectMessageRead(BaseReadSchema):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    media: DirectMessageMediaRead | None
    read_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime

    @classmethod
    def from_message(cls, message: DirectMessage) -> "DirectMessageRead":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            content=message.content,
            media=DirectMessageMediaRead.from_message(message),
            read_at=message.read_at,
            deleted_at=message.deleted_at,
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
