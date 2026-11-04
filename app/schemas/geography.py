from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_AREA_NAME_LENGTH = 150
MAX_LGD_CODE_LENGTH = 10
MAX_AREA_RADIUS_M = 100_000


class GeographySourceMode(StrEnum):
    DIRECT_ADMIN_BOUNDARY = "direct_admin_boundaries"
    DERIVED_FROM_VILLAGE_BOUNDARY = "derived_from_village_boundaries"


class GeographyImportSummary(BaseModel):
    source_mode: GeographySourceMode
    villages_processed: int | None
    state_count: int
    district_count: int
    taluk_count: int
    village_count: int
    created: int
    updated: int
    failed: int


class GeographyAreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_AREA_NAME_LENGTH)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int | None = Field(default=None, gt=0, le=MAX_AREA_RADIUS_M)
    lgd_code: str | None = Field(default=None, min_length=1, max_length=MAX_LGD_CODE_LENGTH)

    @field_validator("name", "lgd_code")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class GisStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lgd_code: str
    name: str


class GisDistrictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    state_id: UUID
    lgd_code: str
    name: str


class GisTalukRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    district_id: UUID
    lgd_code: str
    name: str


class GisVillageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    taluk_id: UUID
    lgd_code: str
    name: str


class ReverseGeocodeQuery(BaseModel):
    latitude: float
    longitude: float


class ReverseGeocodeResult(BaseModel):
    state: GisStateRead
    district: GisDistrictRead
    taluk: GisTalukRead


class ReverseGeocodeAddressResult(BaseModel):
    location_name: str


class AddressSuggestion(BaseModel):
    location_name: str
