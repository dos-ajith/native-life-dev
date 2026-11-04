from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.messages import PopularPlaceMessages
from app.models.gis_district import GisDistrict
from app.models.popular_place import PopularPlace
from app.schemas.base import BaseReadSchema
from app.schemas.native_place import DistrictRef, NativePlaceRead
from app.schemas.post import Latitude, Longitude
from app.schemas.validators import NonBlankStr

DEFAULT_POPULAR_PLACES_LIMIT = 20
MAX_POPULAR_PLACES_LIMIT = 50
METERS_PER_KM = 1000
DISTANCE_KM_DECIMALS = 2

PopularPlaceSearch = Annotated[NonBlankStr, Field(min_length=2, max_length=100)]


class PopularPlaceListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    q: PopularPlaceSearch | None = None
    district_id: UUID | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    limit: int = Field(default=DEFAULT_POPULAR_PLACES_LIMIT, ge=1, le=MAX_POPULAR_PLACES_LIMIT)

    @model_validator(mode="after")
    def _validate(self) -> "PopularPlaceListQuery":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(PopularPlaceMessages.LOCATION_INCOMPLETE)
        return self

    @property
    def is_unfiltered(self) -> bool:
        return self.q is None and self.district_id is None and self.latitude is None


class PopularPlaceCreate(BaseModel):
    village_id: UUID
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class PopularPlaceUpdate(BaseModel):
    village_id: UUID | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PopularPlaceItem(NativePlaceRead):
    is_my_native_place: bool
    distance_km: float | None

    @classmethod
    def from_popular_place(
        cls,
        popular_place: PopularPlace,
        distance_m: float | None,
        primary_village_id: UUID | None,
    ) -> "PopularPlaceItem":
        return cls(
            **{
                **NativePlaceRead.from_village(popular_place.village).model_dump(),
                "image_url": popular_place.image_url,
            },
            is_my_native_place=popular_place.village_id == primary_village_id,
            distance_km=(
                round(distance_m / METERS_PER_KM, DISTANCE_KM_DECIMALS)
                if distance_m is not None
                else None
            ),
        )


class PopularPlacesRead(BaseModel):
    district: DistrictRef | None
    places: list[PopularPlaceItem]

    @classmethod
    def create(
        cls,
        district: GisDistrict | None,
        places: list[tuple[PopularPlace, float | None]],
        primary_village_id: UUID | None,
    ) -> "PopularPlacesRead":
        return cls(
            district=DistrictRef(id=district.id, name=district.name) if district else None,
            places=[
                PopularPlaceItem.from_popular_place(place, distance_m, primary_village_id)
                for place, distance_m in places
            ],
        )


class PopularPlaceAdminRead(BaseReadSchema):
    id: UUID
    place: NativePlaceRead
    image_url: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_popular_place(cls, popular_place: PopularPlace) -> "PopularPlaceAdminRead":
        return cls(
            id=popular_place.id,
            place=NativePlaceRead.from_village(popular_place.village),
            image_url=popular_place.image_url,
            sort_order=popular_place.sort_order,
            is_active=popular_place.is_active,
            created_at=popular_place.created_at,
            updated_at=popular_place.updated_at,
        )
