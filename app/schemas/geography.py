from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GeographySourceMode(StrEnum):
    DIRECT_ADMIN_BOUNDARY = "direct_admin_boundaries"
    DERIVED_FROM_VILLAGE_BOUNDARY = "derived_from_village_boundaries"


class GeographyImportSummary(BaseModel):
    source_mode: GeographySourceMode
    villages_processed: int | None
    state_count: int
    district_count: int
    taluk_count: int
    created: int
    updated: int
    failed: int


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


class ReverseGeocodeQuery(BaseModel):
    latitude: float
    longitude: float


class ReverseGeocodeResult(BaseModel):
    state: GisStateRead
    district: GisDistrictRead
    taluk: GisTalukRead
