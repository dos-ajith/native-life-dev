from pydantic import BaseModel


class GeographyImportSummary(BaseModel):
    state_count: int
    district_count: int
    taluk_count: int
    created: int
    updated: int
    failed: int
