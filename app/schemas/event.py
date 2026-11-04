from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.messages import EventMessages
from app.core.timezone import app_now, to_naive_app_time
from app.models.event import EventStatus
from app.schemas.base import BaseReadSchema
from app.schemas.category import CategoryRef
from app.schemas.post import Latitude, Longitude, NearbyRadiusKm, PostAuthorRead
from app.schemas.user import Phone
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.event_image import EventImage
    from app.models.user import User

MAX_EVENT_IMAGES = 6
MAX_EVENT_CAPTION_LENGTH = 100
EventTitle = Annotated[NonBlankStr, Field(max_length=255)]
EventDescription = Annotated[NonBlankStr, Field(max_length=5000)]
EventVenueName = Annotated[NonBlankStr, Field(max_length=500)]
EventOrganizerName = Annotated[NonBlankStr, Field(max_length=150)]
EventSearch = Annotated[NonBlankStr, Field(max_length=100)]
EventCaption = Annotated[NonBlankStr, Field(max_length=MAX_EVENT_CAPTION_LENGTH)]


def _ensure_not_in_past(value: datetime | None) -> datetime | None:
    if value is not None and to_naive_app_time(value) < to_naive_app_time(app_now()):
        raise ValueError(EventMessages.START_IN_PAST)
    return value


def _ensure_ends_after_start(starts_at: datetime | None, ends_at: datetime | None) -> None:
    if (
        starts_at is not None
        and ends_at is not None
        and to_naive_app_time(ends_at) <= to_naive_app_time(starts_at)
    ):
        raise ValueError(EventMessages.END_BEFORE_START)


class EventCreate(BaseModel):
    category_id: UUID
    title: EventTitle
    description: EventDescription
    venue_name: EventVenueName
    latitude: Latitude
    longitude: Longitude
    starts_at: datetime
    ends_at: datetime
    organizer_name: EventOrganizerName | None = None
    organizer_phone: Phone | None = None

    _start_not_in_past = field_validator("starts_at")(_ensure_not_in_past)

    @model_validator(mode="after")
    def _validate_dates(self) -> "EventCreate":
        _ensure_ends_after_start(self.starts_at, self.ends_at)
        return self


class EventUpdate(BaseModel):
    category_id: UUID | None = None
    title: EventTitle | None = None
    description: EventDescription | None = None
    venue_name: EventVenueName | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    organizer_name: EventOrganizerName | None = None
    organizer_phone: Phone | None = None

    _start_not_in_past = field_validator("starts_at")(_ensure_not_in_past)

    @model_validator(mode="after")
    def _validate(self) -> "EventUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(EventMessages.LOCATION_INCOMPLETE)
        _ensure_ends_after_start(self.starts_at, self.ends_at)
        return self


class EventListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    category_id: UUID | None = None
    q: EventSearch | None = None
    from_date: date | None = None
    to_date: date | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    radius_km: NearbyRadiusKm | None = None
    village_id: UUID | None = Field(
        default=None,
        description="Temporary native place switch; replaces your primary and secondary places.",
    )

    @model_validator(mode="after")
    def _validate(self) -> "EventListQuery":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(EventMessages.LOCATION_INCOMPLETE)
        if self.radius_km is not None and self.latitude is None:
            raise ValueError(EventMessages.RADIUS_REQUIRES_LOCATION)
        if self.from_date and self.to_date and self.to_date < self.from_date:
            raise ValueError(EventMessages.DATE_RANGE_INVALID)
        return self


class EventImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    image_url: str
    caption: str | None
    sort_order: int


class EventOrganizerRead(BaseModel):
    name: str
    phone: str | None


class EventRead(BaseReadSchema):
    id: UUID
    status: EventStatus
    title: str
    description: str
    category: CategoryRef
    venue_name: str
    latitude: float
    longitude: float
    starts_at: datetime
    ends_at: datetime
    is_featured: bool
    organizer: EventOrganizerRead
    author: PostAuthorRead
    images: list[EventImageRead]
    is_mine: bool
    distance_km: float | None = None

    @classmethod
    def from_event(
        cls,
        event: "Event",
        author: "User",
        images: list["EventImage"],
        viewer: "User",
        distance_km: float | None = None,
    ) -> "EventRead":
        return cls(
            id=event.id,
            status=event.status,
            title=event.title,
            description=event.description,
            category=CategoryRef(id=event.category.id, name=event.category.name),
            venue_name=event.venue_name,
            latitude=event.latitude,
            longitude=event.longitude,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            is_featured=event.is_featured,
            organizer=EventOrganizerRead(name=event.organizer_name, phone=event.organizer_phone),
            author=PostAuthorRead.from_user(author),
            images=[EventImageRead.model_validate(image) for image in images],
            is_mine=event.user_id == viewer.id,
            distance_km=distance_km,
        )
