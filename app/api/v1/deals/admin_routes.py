from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.deals.permissions import DealAdminViewDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.schemas.deal import AdminDealListQuery, DealRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.deal_admin_service import DealAdminService

router = APIRouter(prefix="/admin/deals", tags=[ApiTag.ADMIN_DEALS])


@router.get("", response_model=SuccessResponse[Page[DealRead]])
def list_deals_as_admin(
    db: DbSessionDep,
    admin: DealAdminViewDep,
    params: PaginationDep,
    filters: Annotated[AdminDealListQuery, Query()],
) -> SuccessResponse[Page[DealRead]]:
    deals, total = DealAdminService(db).list_all(admin, filters.status, filters.search, params)
    return SuccessResponse(
        message=DealMessages.ADMIN_LIST_RETRIEVED,
        data=Page[DealRead].create(items=deals, total=total, params=params),
    )
