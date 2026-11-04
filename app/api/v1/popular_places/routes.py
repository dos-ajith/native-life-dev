from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSessionDep, OptionalActiveUserDep
from app.core.messages import PopularPlaceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.popular_place import PopularPlaceListQuery, PopularPlacesRead
from app.schemas.response import SuccessResponse
from app.services.popular_place_service import PopularPlaceService

router = APIRouter(prefix="/native-places/popular", tags=[ApiTag.NATIVE_PLACES])


@router.get("", response_model=SuccessResponse[PopularPlacesRead])
def list_popular_places(
    db: DbSessionDep,
    current_user: OptionalActiveUserDep,
    query: Annotated[PopularPlaceListQuery, Query()],
) -> SuccessResponse[PopularPlacesRead]:
    result = PopularPlaceService(db).list_for_viewer(current_user, query)
    return SuccessResponse(
        message=PopularPlaceMessages.LIST_RETRIEVED,
        data=PopularPlacesRead.create(result.district, result.places, result.primary_village_id),
    )
