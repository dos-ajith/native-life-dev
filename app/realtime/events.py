import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.core.timezone import app_now


class ClientMessageType(enum.StrEnum):
    AUTH = "auth"
    PING = "ping"
    TYPING = "typing"


class ServerMessageType(enum.StrEnum):
    AUTH_OK = "auth.ok"
    PONG = "pong"


class RealtimeEventType(enum.StrEnum):
    NOTIFICATION_CREATED = "notification.created"
    NOTIFICATION_READ = "notification.read"
    FOLLOW_REQUEST_CREATED = "follow_request.created"
    FOLLOW_REQUEST_ACCEPTED = "follow_request.accepted"
    FOLLOW_REQUEST_REMOVED = "follow_request.removed"
    ROLE_UPGRADE_REQUEST_CREATED = "role_upgrade_request.created"
    ROLE_UPGRADE_REQUEST_APPROVED = "role_upgrade_request.approved"
    ROLE_UPGRADE_REQUEST_REJECTED = "role_upgrade_request.rejected"
    PRESENCE_CHANGED = "presence.changed"
    DIRECT_MESSAGE_TYPING = "direct_message.typing"
    DIRECT_MESSAGE_CREATED = "direct_message.created"
    DIRECT_MESSAGES_READ = "direct_message.read"
    COMMUNITY_MESSAGE_CREATED = "community.message.created"
    COMMUNITY_MESSAGE_DELETED = "community.message.deleted"
    COMMUNITY_POST_CREATED = "community.post.created"
    COMMUNITY_POLL_CREATED = "community.poll.created"
    COMMUNITY_READ = "community.read"
    DELIVERY_LOCATION_UPDATED = "delivery.location.updated"


class AuthMessage(BaseModel):
    type: Literal[ClientMessageType.AUTH]
    token: str = Field(min_length=1)


class TypingMessage(BaseModel):
    type: Literal[ClientMessageType.TYPING]
    user_id: UUID
    is_typing: bool


class ClientMessage(BaseModel):
    type: str


class ControlMessage(BaseModel):
    type: ServerMessageType


class RealtimeEvent(BaseModel):
    type: str
    id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=app_now)
    data: dict[str, Any] = Field(default_factory=dict)
