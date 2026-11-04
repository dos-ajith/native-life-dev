from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.schemas.deal import DealExploreQuery, DealRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.deal_service import DealService

router = APIRouter(prefix="/deals", tags=[ApiTag.DEAL_EXPLORE])


@router.get("/explore", response_model=SuccessResponse[Page[DealRead]])
def explore_deals(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[DealExploreQuery, Query()],
) -> SuccessResponse[Page[DealRead]]:
    deals, total = DealService(db).explore(current_user, query, params)
    return SuccessResponse(
        message=DealMessages.LIST_RETRIEVED,
        data=Page[DealRead].create(items=deals, total=total, params=params),
    )
