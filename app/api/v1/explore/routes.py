from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import ExploreMessages
from app.core.openapi_tags import ApiTag
from app.schemas.business import BusinessDiscoveryQuery, BusinessSummaryRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.business_service import BusinessService

router = APIRouter(prefix="/explore", tags=[ApiTag.EXPLORE])


@router.get("/businesses", response_model=SuccessResponse[Page[BusinessSummaryRead]])
def explore_businesses(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[BusinessDiscoveryQuery, Query()],
) -> SuccessResponse[Page[BusinessSummaryRead]]:
    items, total = BusinessService(db).search_nearby(query, params, current_user)
    page = Page[BusinessSummaryRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=ExploreMessages.BUSINESSES_RETRIEVED, data=page)
