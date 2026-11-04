from datetime import date
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.messages import LostFoundMessages
from app.core.timezone import app_now
from app.models.lost_found_item import LostFoundKind, LostFoundStatus
from app.schemas.base import BaseReadSchema
from app.schemas.category import CategoryRef
from app.schemas.post import Latitude, Longitude, NearbyRadiusKm, PostAuthorRead
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.lost_found_image import LostFoundImage
    from app.models.lost_found_item import LostFoundItem
    from app.models.user import User

MAX_LOST_FOUND_IMAGES = 4
LostFoundTitle = Annotated[NonBlankStr, Field(max_length=255)]
LostFoundDescription = Annotated[NonBlankStr, Field(max_length=500)]
LostFoundLocationName = Annotated[NonBlankStr, Field(max_length=500)]
LostFoundContact = Annotated[NonBlankStr, Field(max_length=150)]
LostFoundSearch = Annotated[NonBlankStr, Field(max_length=100)]
LostFoundResponseNote = Annotated[NonBlankStr, Field(max_length=300)]


def _ensure_not_in_future(value: date | None) -> date | None:
    if value is not None and value > app_now().date():
        raise ValueError(LostFoundMessages.DATE_IN_FUTURE)
    return value


class LostFoundCreate(BaseModel):
    kind: LostFoundKind
    category_id: UUID
    title: LostFoundTitle
    description: LostFoundDescription
    location_name: LostFoundLocationName
    latitude: Latitude
    longitude: Longitude
    occurred_on: date
    contact_info: LostFoundContact

    _date_not_in_future = field_validator("occurred_on")(_ensure_not_in_future)


class LostFoundResponseCreate(BaseModel):
    note: LostFoundResponseNote | None = None


class LostFoundUpdate(BaseModel):
    category_id: UUID | None = None
    title: LostFoundTitle | None = None
    description: LostFoundDescription | None = None
    location_name: LostFoundLocationName | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    occurred_on: date | None = None
    contact_info: LostFoundContact | None = None

    _date_not_in_future = field_validator("occurred_on")(_ensure_not_in_future)

    @model_validator(mode="after")
    def _validate_location(self) -> "LostFoundUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(LostFoundMessages.LOCATION_INCOMPLETE)
        return self


class LostFoundListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: LostFoundKind | None = None
    status: LostFoundStatus = LostFoundStatus.OPEN
    category_id: UUID | None = None
    q: LostFoundSearch | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    radius_km: NearbyRadiusKm | None = None
    village_id: UUID | None = Field(
        default=None,
        description="Temporary native place switch; replaces your primary and secondary places.",
    )

    @model_validator(mode="after")
    def _validate_location(self) -> "LostFoundListQuery":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(LostFoundMessages.LOCATION_INCOMPLETE)
        if self.radius_km is not None and self.latitude is None:
            raise ValueError(LostFoundMessages.RADIUS_REQUIRES_LOCATION)
        return self


class LostFoundImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    image_url: str
    sort_order: int


class LostFoundRead(BaseReadSchema):
    id: UUID
    kind: LostFoundKind
    status: LostFoundStatus
    title: str
    description: str
    category: CategoryRef
    location_name: str
    latitude: float
    longitude: float
    occurred_on: date
    contact_info: str
    author: PostAuthorRead
    images: list[LostFoundImageRead]
    is_mine: bool
    distance_km: float | None = None

    @classmethod
    def from_item(
        cls,
        item: "LostFoundItem",
        author: "User",
        images: list["LostFoundImage"],
        viewer: "User",
        distance_km: float | None = None,
    ) -> "LostFoundRead":
        return cls(
            id=item.id,
            kind=item.kind,
            status=item.status,
            title=item.title,
            description=item.description,
            category=CategoryRef(id=item.category.id, name=item.category.name),
            location_name=item.location_name,
            latitude=item.latitude,
            longitude=item.longitude,
            occurred_on=item.occurred_on,
            contact_info=item.contact_info,
            author=PostAuthorRead.from_user(author),
            images=[LostFoundImageRead.model_validate(image) for image in images],
            is_mine=item.user_id == viewer.id,
            distance_km=distance_km,
        )
