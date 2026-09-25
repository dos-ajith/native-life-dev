from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, ReverseGeocodeQueryDep
from app.core.messages import GeographyMessages
from app.schemas.geography import (
    GisDistrictRead,
    GisStateRead,
    GisTalukRead,
    ReverseGeocodeAddressResult,
    ReverseGeocodeResult,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.geography_service import GeographyService

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/states", response_model=SuccessResponse[Page[GisStateRead]])
def list_states(db: DbSessionDep, params: PaginationDep) -> SuccessResponse[Page[GisStateRead]]:
    items, total = GeographyService(db).list_states(params)
    page = Page[GisStateRead].create(
        items=[GisStateRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.STATES_RETRIEVED, data=page)


@router.get("/states/{state_id}/districts", response_model=SuccessResponse[Page[GisDistrictRead]])
def list_districts(
    state_id: UUID, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[GisDistrictRead]]:
    items, total = GeographyService(db).list_districts(state_id, params)
    page = Page[GisDistrictRead].create(
        items=[GisDistrictRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.DISTRICTS_RETRIEVED, data=page)


@router.get(
    "/districts/{district_id}/taluks", response_model=SuccessResponse[Page[GisTalukRead]]
)
def list_taluks(
    district_id: UUID, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[GisTalukRead]]:
    items, total = GeographyService(db).list_taluks(district_id, params)
    page = Page[GisTalukRead].create(
        items=[GisTalukRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=GeographyMessages.TALUKS_RETRIEVED, data=page)


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
