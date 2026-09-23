from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.post_media import PostMediaType
from app.models.user_settings_enums import AIResponseStyle
from app.schemas.post import PostDetailRead, PostMediaRead
from app.schemas.validators import NonBlankStr

AskPrompt = Annotated[NonBlankStr, Field(max_length=2000)]

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
    source: str = "Native Life"

    @classmethod
    def from_detail(cls, detail: PostDetailRead) -> "PostReferenceRead":
        return cls(
            post_id=detail.id,
            slug=detail.slug,
            title=detail.title,
            summary=_content_snippet(detail.content),
            author_name=detail.author.name,
            image_url=_primary_image_url(detail.media),
            tags=[tag.name for tag in detail.tags],
        )


class AIPersonalizationContext(BaseModel):
    ai_enabled: bool
    personalization_enabled: bool
    preferred_language: str
    response_style: AIResponseStyle
    preferred_category_names: list[str]
    preferred_district_names: list[str]


class AIAskRequest(BaseModel):
    prompt: AskPrompt


class AIAskResponse(BaseModel):
    answer: str
    posts: list[PostReferenceRead] = []
