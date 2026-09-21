from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GeographyImportSummary(BaseModel):
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
