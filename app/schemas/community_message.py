from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.community_message import CommunityMessage
from app.schemas.base import BaseReadSchema
from app.schemas.user import UserSummaryRead
from app.schemas.validators import NonBlankStr

MAX_MESSAGE_LENGTH = 2000
DEFAULT_HISTORY_LIMIT = 30
MAX_HISTORY_LIMIT = 100

REPLY_PREVIEW_LENGTH = 100
REPLY_PREVIEW_SUFFIX = "..."

MessageContent = Annotated[NonBlankStr, Field(max_length=MAX_MESSAGE_LENGTH)]


class MessageReplyRead(BaseModel):
    id: UUID
    sender_name: str
    content: str

    @classmethod
    def from_message(cls, message: CommunityMessage) -> "MessageReplyRead":
        content = message.content
        if len(content) > REPLY_PREVIEW_LENGTH:
            content = content[:REPLY_PREVIEW_LENGTH].rstrip() + REPLY_PREVIEW_SUFFIX
        return cls(
            id=message.id,
            sender_name=f"{message.sender.first_name} {message.sender.last_name}",
            content=content,
        )


def reply_preview(message: CommunityMessage) -> MessageReplyRead | None:
    return MessageReplyRead.from_message(message.reply_to) if message.reply_to else None


class CommunityMessageCreate(BaseModel):
    content: MessageContent
    reply_to_id: UUID | None = None


class CommunityMessageRead(BaseReadSchema):
    id: UUID
    community_id: UUID
    sender: UserSummaryRead
    content: str
    reply_to: MessageReplyRead | None
    created_at: datetime

    @classmethod
    def from_message(cls, message: CommunityMessage) -> "CommunityMessageRead":
        return cls(
            id=message.id,
            community_id=message.community_id,
            sender=UserSummaryRead.model_validate(message.sender),
            content=message.content,
            reply_to=reply_preview(message),
            created_at=message.created_at,
        )


class CommunityMessageHistory(BaseModel):
    items: list[CommunityMessageRead]
    has_more: bool
    next_before_id: UUID | None
