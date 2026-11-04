from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSessionDep, OptionalActiveUserDep, ReverseGeocodeQueryDep, SettingsDep
from app.api.v1.native_places.permissions import NativePlaceSuggestDep
from app.core.messages import NativePlaceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.geography import GisDistrictRead
from app.schemas.native_place import (
    NativePlaceRead,
    NativePlaceSearchItem,
    NativePlaceSearchResult,
    NativePlaceSuggestionCreate,
    NativePlaceSuggestionRead,
)
from app.schemas.response import SuccessResponse
from app.schemas.village_boundary import VillageBoundaryRead
from app.services.native_place_suggestion_service import NativePlaceSuggestionService
from app.services.user_native_place_service import UserNativePlaceService
from app.services.village_boundary_service import VillageBoundaryService

MIN_SEARCH_LENGTH = 2
MAX_SEARCH_LENGTH = 100
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 20
BOUNDARY_CACHE_CONTROL = "public, max-age=86400"

router = APIRouter(prefix="/native-places", tags=[ApiTag.NATIVE_PLACES])


@router.get("/search", response_model=SuccessResponse[NativePlaceSearchResult])
def search_native_places(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: OptionalActiveUserDep,
    q: Annotated[str, Query(min_length=MIN_SEARCH_LENGTH, max_length=MAX_SEARCH_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = DEFAULT_SEARCH_LIMIT,
) -> SuccessResponse[NativePlaceSearchResult]:
    service = UserNativePlaceService(db)
    villages, districts = service.search(q, limit, settings.default_state_lgd_code)
    primary_village_id = (
        service.primary_village_id(current_user) if current_user is not None else None
    )
    result = NativePlaceSearchResult(
        places=[
            NativePlaceSearchItem(
                **NativePlaceRead.from_village(village).model_dump(),
                is_my_native_place=village.id == primary_village_id,
            )
            for village in villages
        ],
        districts=[GisDistrictRead.model_validate(district) for district in districts],
    )
    return SuccessResponse(message=NativePlaceMessages.SEARCH_RETRIEVED, data=result)


@router.get("/current", response_model=SuccessResponse[NativePlaceRead])
def get_native_place_for_current_location(
    db: DbSessionDep, params: ReverseGeocodeQueryDep
) -> SuccessResponse[NativePlaceRead]:
    village = UserNativePlaceService(db).resolve_current_location(params.latitude, params.longitude)
    return SuccessResponse(
        message=NativePlaceMessages.CURRENT_LOCATION_RESOLVED,
        data=NativePlaceRead.from_village(village),
    )


@router.get("/{village_id}/boundary", response_model=SuccessResponse[VillageBoundaryRead])
def get_native_place_boundary(
    village_id: UUID, response: Response, db: DbSessionDep
) -> SuccessResponse[VillageBoundaryRead]:
    response.headers["Cache-Control"] = BOUNDARY_CACHE_CONTROL
    result = VillageBoundaryService(db).for_village(village_id)
    return SuccessResponse(
        message=NativePlaceMessages.BOUNDARY_RETRIEVED,
        data=VillageBoundaryRead.from_result(result),
    )


@router.post(
    "/suggestions",
    response_model=SuccessResponse[NativePlaceSuggestionRead],
    status_code=status.HTTP_201_CREATED,
)
def suggest_native_place(
    payload: NativePlaceSuggestionCreate, db: DbSessionDep, current_user: NativePlaceSuggestDep
) -> SuccessResponse[NativePlaceSuggestionRead]:
    suggestion = NativePlaceSuggestionService(db).suggest(payload, current_user)
    return SuccessResponse(
        message=NativePlaceMessages.SUGGESTED,
        data=NativePlaceSuggestionRead.from_suggestion(suggestion),
    )
