import enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.post import PostDetailRead


class UpdateAreaSource(enum.StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TEMPORARY = "temporary"


class UpdateFeedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    village_id: UUID | None = Field(
        default=None,
        description=(
            "Temporary native place switch. When set, updates are recommended for this "
            "place only instead of your primary and secondary native places."
        ),
    )


class UpdateFeedItem(PostDetailRead):
    distance_km: float
    area: UpdateAreaSource

    @classmethod
    def from_detail(
        cls, detail: PostDetailRead, area: UpdateAreaSource, distance_km: float
    ) -> "UpdateFeedItem":
        return cls(
            **{name: getattr(detail, name) for name in PostDetailRead.model_fields},
            area=area,
            distance_km=distance_km,
        )
