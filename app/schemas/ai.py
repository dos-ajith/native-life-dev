import enum
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from pydantic import Base64Bytes, BaseModel, Field, model_validator

from app.ai.voice.avatars import DEFAULT_AVATAR_ID, AvatarGender
from app.core.messages import AIMessages, PostMessages
from app.models.ai_draft import AIDraftKind
from app.models.post_media import PostMediaType
from app.models.user_settings_enums import AIResponseStyle
from app.schemas.ai_draft import AICreatedEntityRead
from app.schemas.post import Latitude, Longitude, NearbyRadiusKm, PostDetailRead, PostMediaRead
from app.schemas.validators import NonBlankStr

AskPrompt = Annotated[NonBlankStr, Field(max_length=2000)]


@dataclass(frozen=True)
class UserLocation:
    latitude: float
    longitude: float
    radius_km: float | None = None


_CONTENT_SNIPPET_LENGTH = 240


def _content_snippet(content: str | None) -> str | None:
    if content is None:
        return None
    stripped = content.strip()
    if len(stripped) <= _CONTENT_SNIPPET_LENGTH:
        return stripped
    return stripped[:_CONTENT_SNIPPET_LENGTH].rstrip() + "…"


def _primary_image_url(media: list[PostMediaRead]) -> str | None:
    for item in media:
        if item.media_type == PostMediaType.IMAGE:
            return item.file_url
    for item in media:
        if item.thumbnail_url:
            return item.thumbnail_url
    return None


class PostReferenceRead(BaseModel):
    """Compact post reference for the AI: used both as a tool result (token-efficient
    for the model) and returned to API clients as structured data alongside the
    answer, so the app can render a card/link without parsing the prose."""

    post_id: UUID
    slug: str
    title: str | None
    summary: str | None
    author_name: str
    image_url: str | None
    tags: list[str]
    location_name: str | None = None
    distance_km: float | None = None
    source: str = "Native Life"

    @classmethod
    def from_detail(
        cls, detail: PostDetailRead, distance_km: float | None = None
    ) -> "PostReferenceRead":
        return cls(
            distance_km=distance_km,
            post_id=detail.id,
            slug=detail.slug,
            title=detail.title,
            summary=_content_snippet(detail.content),
            author_name=detail.author.name,
            image_url=_primary_image_url(detail.media),
            tags=[tag.name for tag in detail.tags],
            location_name=detail.location_name,
        )


class AIPersonalizationContext(BaseModel):
    ai_enabled: bool
    personalization_enabled: bool
    preferred_language: str
    response_style: AIResponseStyle
    preferred_category_names: list[str]
    preferred_district_names: list[str]


class AIAskMode(enum.StrEnum):
    CHAT = "chat"
    LIVE = "live"


class AIAskRequest(BaseModel):
    mode: AIAskMode = AIAskMode.CHAT
    prompt: AskPrompt | None = None
    audio_base64: Base64Bytes | None = None
    language: Annotated[str | None, Field(max_length=10)] = None
    avatar_id: str = DEFAULT_AVATAR_ID
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    radius_km: NearbyRadiusKm | None = None

    @model_validator(mode="after")
    def _validate_input(self) -> "AIAskRequest":
        if (self.prompt is None) == (self.audio_base64 is None):
            raise ValueError(AIMessages.PROMPT_OR_AUDIO_REQUIRED)
        if self.audio_base64 is not None and self.mode != AIAskMode.LIVE:
            raise ValueError(AIMessages.AUDIO_REQUIRES_LIVE_MODE)
        return self

    @model_validator(mode="after")
    def _validate_location(self) -> "AIAskRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(PostMessages.LOCATION_INCOMPLETE)
        if self.radius_km is not None and self.latitude is None:
            raise ValueError(PostMessages.RADIUS_REQUIRES_LOCATION)
        return self

    @property
    def location(self) -> UserLocation | None:
        if self.latitude is None or self.longitude is None:
            return None
        return UserLocation(self.latitude, self.longitude, self.radius_km)


class AISuggestionRead(BaseModel):
    id: str
    title: str
    subtitle: str
    prompt: str


class AIWelcomeRead(BaseModel):
    greeting: str
    intro: str
    hint: str
    place_name: str | None
    suggestions_title: str
    suggestions: list[AISuggestionRead]


class AIAvatarRead(BaseModel):
    id: str
    name: str
    gender: AvatarGender


class AIInputKind(enum.StrEnum):
    TEXT = "text"
    DATETIME = "datetime"
    CHOICE = "choice"
    CONFIRM = "confirm"


class AIOptionRead(BaseModel):
    id: str
    label: str
    prompt: str


class AINextStepRead(BaseModel):
    flow: AIDraftKind
    field: str | None
    input: AIInputKind
    options: list[AIOptionRead] = []


class AIAskResponse(BaseModel):
    answer: str
    posts: list[PostReferenceRead] = []
    created: AICreatedEntityRead | None = None
    next_step: AINextStepRead | None = None
    transcript: str | None = None
    audio_url: str | None = None
