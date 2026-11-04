from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.messages import PostMessages
from app.models.community_member import CommunityMemberStatus
from app.models.post import PostAudience, PostStatus, PostVisibility
from app.models.post_like import ReactionType
from app.models.post_media import PostMediaType
from app.schemas.base import BaseReadSchema
from app.schemas.pagination import Page
from app.schemas.tag import TagName, TagRead
from app.schemas.validators import AlphanumericStr, NonBlankStr
from app.utils.relative_time import format_relative_time

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.post_media import PostMedia
    from app.models.tag import Tag
    from app.models.user import User

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
PostTitle = Annotated[AlphanumericStr, Field(max_length=255)]
PostContent = NonBlankStr
PostLocationName = Annotated[NonBlankStr, Field(max_length=500)]
MAX_NEARBY_RADIUS_KM = 50
NearbyRadiusKm = Annotated[float, Field(gt=0, le=MAX_NEARBY_RADIUS_KM)]


class PostCommunityRead(BaseModel):
    id: UUID
    name: str
    image_url: str | None
    my_membership: CommunityMemberStatus | None


class PostRead(BaseReadSchema):
    id: UUID
    user_id: UUID
    community_id: UUID | None
    slug: str
    title: str | None
    content: str | None
    status: PostStatus
    audience: PostAudience
    visibility: PostVisibility
    latitude: float | None
    longitude: float | None
    location_name: str | None
    scheduled_at: datetime | None
    published_at: datetime | None
    published_by: UUID | None
    created_at: datetime
    updated_at: datetime


class PostCreate(BaseModel):
    community_id: UUID | None = None
    title: PostTitle | None = None
    content: PostContent | None = None
    status: PostStatus = PostStatus.DRAFT
    audience: PostAudience = PostAudience.EVERYONE
    visibility: PostVisibility | None = None
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
        if self.visibility == PostVisibility.PRIVATE and self.community_id is None:
            raise ValueError(PostMessages.PRIVATE_REQUIRES_COMMUNITY)
        if self.status == PostStatus.BLOCKED:
            raise ValueError(PostMessages.STATUS_BLOCKED_NOT_ALLOWED)
        return self


class PostUpdate(BaseModel):
    title: PostTitle | None = None
    content: PostContent | None = None
    status: PostStatus | None = None
    audience: PostAudience | None = None
    visibility: PostVisibility | None = None
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
        if self.status == PostStatus.BLOCKED:
            raise ValueError(PostMessages.STATUS_BLOCKED_NOT_ALLOWED)
        return self


class AdminPostListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: PostStatus | None = None
    audience: PostAudience | None = None
    visibility: PostVisibility | None = None
    user_id: UUID | None = Field(default=None, description="Filter posts by author.")
    community_id: UUID | None = None
    q: NonBlankStr | None = Field(default=None, description="Search title, content and tags.")


class PostBlock(BaseModel):
    reason: NonBlankStr | None = None


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
    community_id: UUID | None
    community: PostCommunityRead | None = None
    slug: str
    title: str | None
    content: str | None
    status: PostStatus
    audience: PostAudience
    visibility: PostVisibility
    latitude: float | None
    longitude: float | None
    location_name: str | None
    scheduled_at: datetime | None
    published_at: datetime | None
    published_at_relative: str | None = None
    published_by: UUID | None
    created_at: datetime
    updated_at: datetime
    media: list[PostMediaRead]
    tags: list[TagRead]
    likes_count: int
    comments_count: int
    shares_count: int
    saved_count: int
    is_saved: bool = False
    reaction_counts: dict[ReactionType, int]
    my_reaction: ReactionType | None = None

    @classmethod
    def from_post(
        cls,
        post: "Post",
        author: "User",
        media: list["PostMedia"],
        tags: list["Tag"],
        is_saved: bool = False,
        reaction_counts: dict[ReactionType, int] | None = None,
        my_reaction: ReactionType | None = None,
        community: PostCommunityRead | None = None,
    ) -> "PostDetailRead":
        counts = reaction_counts or {}
        return cls(
            id=post.id,
            author=PostAuthorRead.from_user(author),
            community_id=post.community_id,
            community=community,
            slug=post.slug,
            title=post.title,
            content=post.content,
            status=post.status,
            audience=post.audience,
            visibility=post.visibility,
            latitude=post.latitude,
            longitude=post.longitude,
            location_name=post.location_name,
            scheduled_at=post.scheduled_at,
            published_at=post.published_at,
            published_at_relative=(
                format_relative_time(post.published_at) if post.published_at else None
            ),
            published_by=post.published_by,
            created_at=post.created_at,
            updated_at=post.updated_at,
            media=[PostMediaRead.model_validate(item) for item in media],
            tags=[TagRead.model_validate(item) for item in tags],
            likes_count=post.likes_count,
            comments_count=post.comments_count,
            shares_count=post.shares_count,
            saved_count=post.saved_count,
            is_saved=is_saved,
            reaction_counts={reaction: counts.get(reaction, 0) for reaction in ReactionType},
            my_reaction=my_reaction,
        )


class PostListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    latitude: Latitude | None = None
    longitude: Longitude | None = None
    radius_km: NearbyRadiusKm | None = None
    user_id: UUID | None = Field(default=None, description="Filter posts by author.")

    @model_validator(mode="after")
    def _validate_location(self) -> "PostListQuery":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(PostMessages.LOCATION_INCOMPLETE)
        if self.radius_km is not None and self.latitude is None:
            raise ValueError(PostMessages.RADIUS_REQUIRES_LOCATION)
        return self

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class NearbyPostDetailRead(PostDetailRead):
    distance_km: float

    @classmethod
    def from_detail(cls, detail: PostDetailRead, distance_km: float) -> "NearbyPostDetailRead":
        return cls(
            **{name: getattr(detail, name) for name in PostDetailRead.model_fields},
            distance_km=distance_km,
        )


class NearbyPostPage(Page[NearbyPostDetailRead]):
    location_based: bool = True
    radius_km: float | None = None
