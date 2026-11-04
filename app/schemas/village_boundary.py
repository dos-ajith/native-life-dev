from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

from app.models.user_native_place import NativePlaceSlot
from app.schemas.native_place import NativePlaceRead

if TYPE_CHECKING:
    from app.services.village_boundary_service import VillageBoundaryResult


class GeoJsonFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any]


class VillageBoundaryRead(BaseModel):
    place: NativePlaceRead
    bbox: list[float]
    center_latitude: float
    center_longitude: float
    feature: GeoJsonFeature

    @classmethod
    def from_result(cls, result: "VillageBoundaryResult") -> "VillageBoundaryRead":
        village = result.village
        boundary = result.boundary
        return cls(
            place=NativePlaceRead.from_village(village),
            bbox=list(boundary.bbox),
            center_latitude=boundary.center[0],
            center_longitude=boundary.center[1],
            feature=GeoJsonFeature(
                geometry=boundary.geometry,
                properties={"village_id": str(village.id), "village_name": village.name},
            ),
        )


class UserNativeBoundaryRead(BaseModel):
    slot: NativePlaceSlot
    boundary: VillageBoundaryRead

    @classmethod
    def from_result(
        cls, slot: NativePlaceSlot, result: "VillageBoundaryResult"
    ) -> "UserNativeBoundaryRead":
        return cls(slot=slot, boundary=VillageBoundaryRead.from_result(result))
