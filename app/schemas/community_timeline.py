import enum
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.community_message import CommunityMessage
from app.models.post_like import ReactionType
from app.models.post_media import PostMediaType
from app.schemas.base import BaseReadSchema
from app.schemas.community_message import MessageReplyRead, reply_preview
from app.schemas.community_poll import CommunityPollRead
from app.schemas.post import PostAuthorRead, PostDetailRead

DEFAULT_TIMELINE_LIMIT = 30
MAX_TIMELINE_LIMIT = 100


class TimelineItemType(enum.StrEnum):
    MESSAGE = "message"
    POST = "post"
    POLL = "poll"


class TimelineMessageRead(BaseReadSchema):
    id: UUID
    sender: PostAuthorRead
    content: str
    reply_to: MessageReplyRead | None
    created_at: datetime

    @classmethod
    def from_message(cls, message: CommunityMessage) -> "TimelineMessageRead":
        return cls(
            id=message.id,
            sender=PostAuthorRead.from_user(message.sender),
            content=message.content,
            reply_to=reply_preview(message),
            created_at=message.created_at,
        )


class TimelineMediaRead(BaseModel):
    id: UUID
    media_type: PostMediaType
    file_url: str
    thumbnail_url: str | None


class TimelineTagRead(BaseModel):
    name: str
    slug: str


class TimelinePostRead(BaseReadSchema):
    id: UUID
    slug: str
    author: PostAuthorRead
    title: str | None
    content: str | None
    location_name: str | None
    published_at: datetime | None
    published_at_relative: str | None
    media: list[TimelineMediaRead]
    tags: list[TimelineTagRead]
    likes_count: int
    comments_count: int
    shares_count: int
    saved_count: int
    is_saved: bool
    reaction_counts: dict[ReactionType, int]
    my_reaction: ReactionType | None

    @classmethod
    def from_detail(cls, detail: PostDetailRead) -> "TimelinePostRead":
        return cls(
            id=detail.id,
            slug=detail.slug,
            author=detail.author,
            title=detail.title,
            content=detail.content,
            location_name=detail.location_name,
            published_at=detail.published_at,
            published_at_relative=detail.published_at_relative,
            media=[
                TimelineMediaRead(
                    id=item.id,
                    media_type=item.media_type,
                    file_url=item.file_url,
                    thumbnail_url=item.thumbnail_url,
                )
                for item in detail.media
            ],
            tags=[TimelineTagRead(name=tag.name, slug=tag.slug) for tag in detail.tags],
            likes_count=detail.likes_count,
            comments_count=detail.comments_count,
            shares_count=detail.shares_count,
            saved_count=detail.saved_count,
            is_saved=detail.is_saved,
            reaction_counts=detail.reaction_counts,
            my_reaction=detail.my_reaction,
        )


class TimelineMessageItem(BaseModel):
    type: Literal[TimelineItemType.MESSAGE] = TimelineItemType.MESSAGE
    message: TimelineMessageRead


class TimelinePostItem(BaseModel):
    type: Literal[TimelineItemType.POST] = TimelineItemType.POST
    post: TimelinePostRead


class TimelinePollItem(BaseModel):
    type: Literal[TimelineItemType.POLL] = TimelineItemType.POLL
    poll: CommunityPollRead


TimelineItemRead = Annotated[
    TimelineMessageItem | TimelinePostItem | TimelinePollItem, Field(discriminator="type")
]


class CommunityTimelineRead(BaseModel):
    items: list[TimelineItemRead]
    has_more: bool
    next_before: str | None
