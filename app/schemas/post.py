from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.post import PostStatus
from app.models.post_media import PostMediaType
from app.schemas.base import BaseReadSchema
from app.schemas.tag import TagName, TagRead
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.post_media import PostMedia
    from app.models.tag import Tag
    from app.models.user import User

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
PostTitle = Annotated[NonBlankStr, Field(max_length=255)]
PostContent = NonBlankStr
PostLocationName = Annotated[NonBlankStr, Field(max_length=500)]


class PostRead(BaseReadSchema):
    id: UUID
    user_id: UUID
    slug: str
    title: str | None
    content: str | None
    status: PostStatus
    latitude: float | None
    longitude: float | None
    location_name: str | None
    scheduled_at: datetime | None
    published_at: datetime | None
    published_by: UUID | None
    created_at: datetime
    updated_at: datetime


class PostCreate(BaseModel):
    title: PostTitle | None = None
    content: PostContent | None = None
    status: PostStatus = PostStatus.DRAFT
    scheduled_at: datetime | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_name: PostLocationName | None = None
    tags: list[TagName] | None = None

    @model_validator(mode="after")
    def _validate(self) -> "PostCreate":
        if self.status == PostStatus.SCHEDULED and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when status is scheduled")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class PostUpdate(BaseModel):
    title: PostTitle | None = None
    content: PostContent | None = None
    status: PostStatus | None = None
    scheduled_at: datetime | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_name: PostLocationName | None = None
    tags: list[TagName] | None = None

    @model_validator(mode="after")
    def _validate(self) -> "PostUpdate":
        if self.status == PostStatus.SCHEDULED and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when status is scheduled")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class PostMediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    media_type: PostMediaType
    file_url: str
    thumbnail_url: str | None
    sort_order: int


class PostWithMediaRead(BaseModel):
    post: PostRead
    media: list[PostMediaRead]
    tags: list[TagRead]


class PostAuthorRead(BaseModel):
    id: UUID
    name: str
    profile_image_url: str | None

    @classmethod
    def from_user(cls, user: "User") -> "PostAuthorRead":
        return cls(
            id=user.id,
            name=f"{user.first_name} {user.last_name}",
            profile_image_url=user.profile_image_url,
        )


class PostDetailRead(BaseReadSchema):
    id: UUID
    author: PostAuthorRead
    slug: str
    title: str | None
    content: str | None
    status: PostStatus
    latitude: float | None
    longitude: float | None
    location_name: str | None
    scheduled_at: datetime | None
    published_at: datetime | None
    published_by: UUID | None
    created_at: datetime
    updated_at: datetime
    media: list[PostMediaRead]
    tags: list[TagRead]
    likes_count: int
    comments_count: int
    shares_count: int
    is_saved: bool = False

    @classmethod
    def from_post(
        cls,
        post: "Post",
        author: "User",
        media: list["PostMedia"],
        tags: list["Tag"],
        is_saved: bool = False,
    ) -> "PostDetailRead":
        return cls(
            id=post.id,
            author=PostAuthorRead.from_user(author),
            slug=post.slug,
            title=post.title,
            content=post.content,
            status=post.status,
            latitude=post.latitude,
            longitude=post.longitude,
            location_name=post.location_name,
            scheduled_at=post.scheduled_at,
            published_at=post.published_at,
            published_by=post.published_by,
            created_at=post.created_at,
            updated_at=post.updated_at,
            media=[PostMediaRead.model_validate(item) for item in media],
            tags=[TagRead.model_validate(item) for item in tags],
            likes_count=post.likes_count,
            comments_count=post.comments_count,
            shares_count=post.shares_count,
            is_saved=is_saved,
        )
