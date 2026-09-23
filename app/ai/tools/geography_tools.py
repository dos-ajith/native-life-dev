from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import AITool, SearchQuery, ToolContext
from app.schemas.ai import PostReferenceRead
from app.schemas.post import Latitude, Longitude, PostDetailRead
from app.services.geography_service import GeographyService
from app.services.post_service import PostService

_MAX_RESULTS = 10
_MAX_NEARBY_RESULTS = 5
_DISTANCE_ROUNDING_METERS = 10


class SearchLocationsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchQuery


class DistrictReferenceRead(BaseModel):
    id: UUID
    name: str
    state_name: str


class SearchLocationsResult(BaseModel):
    items: list[DistrictReferenceRead]


class SearchLocationsTool(AITool[SearchLocationsArgs]):
    name = "search_locations"
    description = (
        "Search existing Native Life GIS districts by free-text place name (e.g. "
        "'Thiruvananthapuram'). Returns up to 10 matching districts with their state."
    )
    args_model = SearchLocationsArgs

    def execute(
        self, context: ToolContext, arguments: SearchLocationsArgs
    ) -> SearchLocationsResult:
        districts = GeographyService(context.db).search_districts(arguments.query, _MAX_RESULTS)
        return SearchLocationsResult(
            items=[
                DistrictReferenceRead(
                    id=district.id, name=district.name, state_name=district.state.name
                )
                for district in districts
            ]
        )


def _round_distance(distance_meters: float) -> int:
    return round(distance_meters / _DISTANCE_ROUNDING_METERS) * _DISTANCE_ROUNDING_METERS


class GetNearbyContentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: Latitude
    longitude: Longitude
    radius_meters: int = Field(default=2000, ge=100, le=50000)


class NearbyPostReferenceRead(PostReferenceRead):
    distance_meters: int

    @classmethod
    def from_detail_with_distance(
        cls, detail: PostDetailRead, distance_meters: float
    ) -> "NearbyPostReferenceRead":
        base = PostReferenceRead.from_detail(detail)
        return cls(**base.model_dump(), distance_meters=_round_distance(distance_meters))


class GetNearbyContentResult(BaseModel):
    items: list[NearbyPostReferenceRead]


class GetNearbyContentTool(AITool[GetNearbyContentArgs]):
    name = "get_nearby_content"
    description = (
        "Find Native Life posts the current user is allowed to see within a radius "
        "(in meters, default 2000, max 50000) of a given latitude/longitude. Returns "
        "up to 5 posts ordered by distance, nearest first, each with its distance in "
        "meters."
    )
    args_model = GetNearbyContentArgs

    def execute(
        self, context: ToolContext, arguments: GetNearbyContentArgs
    ) -> GetNearbyContentResult:
        results = PostService(context.db).search_nearby_with_details(
            arguments.latitude,
            arguments.longitude,
            arguments.radius_meters,
            _MAX_NEARBY_RESULTS,
            context.actor,
        )
        return GetNearbyContentResult(
            items=[
                NearbyPostReferenceRead.from_detail_with_distance(detail, distance)
                for detail, distance in results
            ]
        )
