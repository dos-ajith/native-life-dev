from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import (
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    ReverseGeocodeQueryDep,
    SettingsDep,
)
from app.core.messages import GeographyMessages
from app.core.openapi_tags import ApiTag
from app.schemas.geography import (
    AddressSuggestion,
    GisDistrictRead,
    GisStateRead,
    GisTalukRead,
    GisVillageRead,
    ReverseGeocodeAddressResult,
    ReverseGeocodeResult,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.geography_service import GeographyService

MIN_SEARCH_LENGTH = 2
MAX_SEARCH_LENGTH = 100
DEFAULT_SUGGESTION_LIMIT = 10
MAX_SUGGESTION_LIMIT = 20

router = APIRouter(prefix="/geography", tags=[ApiTag.LOCATION])


@router.get("/states", response_model=SuccessResponse[Page[GisStateRead]])
def list_states(db: DbSessionDep, params: PaginationDep) -> SuccessResponse[Page[GisStateRead]]:
    items, total = GeographyService(db).list_states(params)
    page = Page[GisStateRead].create(
        items=[GisStateRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.STATES_RETRIEVED, data=page)


@router.get("/districts", response_model=SuccessResponse[Page[GisDistrictRead]])
def list_districts_with_default_state(
    db: DbSessionDep,
    settings: SettingsDep,
    params: PaginationDep,
    state_id: UUID | None = None,
) -> SuccessResponse[Page[GisDistrictRead]]:
    items, total = GeographyService(db).list_districts_with_default_state(
        state_id, settings.default_state_lgd_code, params
    )
    page = Page[GisDistrictRead].create(
        items=[GisDistrictRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.DISTRICTS_RETRIEVED, data=page)


@router.get("/states/{state_id}/districts", response_model=SuccessResponse[Page[GisDistrictRead]])
def list_districts(
    state_id: UUID, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[GisDistrictRead]]:
    items, total = GeographyService(db).list_districts(state_id, params)
    page = Page[GisDistrictRead].create(
        items=[GisDistrictRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.DISTRICTS_RETRIEVED, data=page)


@router.get("/districts/{district_id}/taluks", response_model=SuccessResponse[Page[GisTalukRead]])
def list_taluks(
    district_id: UUID, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[GisTalukRead]]:
    items, total = GeographyService(db).list_taluks(district_id, params)
    page = Page[GisTalukRead].create(
        items=[GisTalukRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.TALUKS_RETRIEVED, data=page)


@router.get("/taluks/{taluk_id}/villages", response_model=SuccessResponse[Page[GisVillageRead]])
def list_villages(
    taluk_id: UUID, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[GisVillageRead]]:
    items, total = GeographyService(db).list_villages(taluk_id, params)
    page = Page[GisVillageRead].create(
        items=[GisVillageRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.VILLAGES_RETRIEVED, data=page)


@router.get("/reverse", response_model=SuccessResponse[ReverseGeocodeResult])
def reverse_geocode(
    db: DbSessionDep, _: CurrentActiveUserDep, params: ReverseGeocodeQueryDep
) -> SuccessResponse[ReverseGeocodeResult]:
    taluk = GeographyService(db).reverse_geocode(params.latitude, params.longitude)
    result = ReverseGeocodeResult(
        state=GisStateRead.model_validate(taluk.district.state),
        district=GisDistrictRead.model_validate(taluk.district),
        taluk=GisTalukRead.model_validate(taluk),
    )
    return SuccessResponse(message=GeographyMessages.LOCATION_RESOLVED, data=result)


@router.get("/reverse/address", response_model=SuccessResponse[ReverseGeocodeAddressResult])
def reverse_geocode_address(
    db: DbSessionDep, _: CurrentActiveUserDep, params: ReverseGeocodeQueryDep
) -> SuccessResponse[ReverseGeocodeAddressResult]:
    service = GeographyService(db)
    taluk = service.reverse_geocode(params.latitude, params.longitude)
    result = ReverseGeocodeAddressResult(location_name=service.format_location_name(taluk))
    return SuccessResponse(message=GeographyMessages.LOCATION_ADDRESS_RESOLVED, data=result)


@router.get("/search/address", response_model=SuccessResponse[list[AddressSuggestion]])
def search_addresses(
    db: DbSessionDep,
    _: CurrentActiveUserDep,
    q: Annotated[str, Query(min_length=MIN_SEARCH_LENGTH, max_length=MAX_SEARCH_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=MAX_SUGGESTION_LIMIT)] = DEFAULT_SUGGESTION_LIMIT,
) -> SuccessResponse[list[AddressSuggestion]]:
    names = GeographyService(db).suggest_addresses(q, limit)
    suggestions = [AddressSuggestion(location_name=name) for name in names]
    return SuccessResponse(
        message=GeographyMessages.ADDRESS_SUGGESTIONS_RETRIEVED, data=suggestions
    )
