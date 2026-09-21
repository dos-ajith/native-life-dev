from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSessionDep, PaginationDep
from app.core.messages import GeographyMessages
from app.schemas.geography import GisDistrictRead, GisStateRead, GisTalukRead
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
