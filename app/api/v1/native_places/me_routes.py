from fastapi import APIRouter, Response

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import NativePlaceMessages
from app.core.openapi_tags import ApiTag
from app.models.user_native_place import UserNativePlace
from app.schemas.native_place import (
    NativePlaceSelect,
    PrimaryNativePlaceRead,
    UserNativePlaceRead,
)
from app.schemas.response import SuccessResponse
from app.schemas.village_boundary import UserNativeBoundaryRead
from app.services.user_native_place_service import UserNativePlaceService
from app.services.village_boundary_service import VillageBoundaryService

BOUNDARY_CACHE_CONTROL = "private, max-age=86400"

router = APIRouter(prefix="/users/me/native-places", tags=[ApiTag.NATIVE_PLACES])


def _to_response(
    message: str, places: list[UserNativePlace]
) -> SuccessResponse[list[UserNativePlaceRead]]:
    return SuccessResponse(
        message=message,
        data=[UserNativePlaceRead.from_user_native_place(item) for item in places],
    )


@router.get("", response_model=SuccessResponse[list[UserNativePlaceRead]])
def list_my_native_places(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[UserNativePlaceRead]]:
    places = UserNativePlaceService(db).list_for(current_user)
    return _to_response(NativePlaceMessages.LIST_RETRIEVED, places)


@router.get("/boundaries", response_model=SuccessResponse[list[UserNativeBoundaryRead]])
def list_my_native_place_boundaries(
    response: Response, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[UserNativeBoundaryRead]]:
    response.headers["Cache-Control"] = BOUNDARY_CACHE_CONTROL
    boundaries = VillageBoundaryService(db).for_user(current_user)
    return SuccessResponse(
        message=NativePlaceMessages.BOUNDARIES_RETRIEVED,
        data=[UserNativeBoundaryRead.from_result(slot, result) for slot, result in boundaries],
    )


@router.put("/primary", response_model=SuccessResponse[PrimaryNativePlaceRead])
def set_my_primary_native_place(
    payload: NativePlaceSelect, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PrimaryNativePlaceRead]:
    result = UserNativePlaceService(db).set_primary(current_user, payload.village_id)
    return SuccessResponse(
        message=NativePlaceMessages.PRIMARY_SET, data=PrimaryNativePlaceRead.from_result(result)
    )


@router.put("/secondary", response_model=SuccessResponse[list[UserNativePlaceRead]])
def set_my_secondary_native_place(
    payload: NativePlaceSelect, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[UserNativePlaceRead]]:
    places = UserNativePlaceService(db).set_secondary(current_user, payload.village_id)
    return _to_response(NativePlaceMessages.SECONDARY_SET, places)


@router.delete("/secondary", response_model=SuccessResponse[None])
def remove_my_secondary_native_place(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    UserNativePlaceService(db).remove_secondary(current_user)
    return SuccessResponse(message=NativePlaceMessages.SECONDARY_REMOVED, data=None)
