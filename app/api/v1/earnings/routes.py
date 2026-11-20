from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, require_permission
from app.core.messages import EarningMessages
from app.core.openapi_tags import ApiTag
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.earning import (
    AdminEarningListQuery,
    EarningListQuery,
    EarningRead,
    EarningSummaryRead,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.earning_service import EarningService

EarningViewAnyDep = Annotated[User, Depends(require_permission(PermissionName.EARNING_VIEW_ANY))]

me_router = APIRouter(prefix="/me/earnings", tags=[ApiTag.EARNINGS])
business_router = APIRouter(
    prefix="/me/businesses/{business_id}/earnings", tags=[ApiTag.BUSINESS_EARNINGS]
)
admin_router = APIRouter(prefix="/admin/earnings", tags=[ApiTag.ADMIN_EARNINGS])


@me_router.get("", response_model=SuccessResponse[Page[EarningRead]])
def list_my_earnings(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[EarningListQuery, Query()],
) -> SuccessResponse[Page[EarningRead]]:
    items, total = EarningService(db).list_mine(current_user, query, params)
    return SuccessResponse(
        message=EarningMessages.LIST_RETRIEVED,
        data=Page[EarningRead].create(items=items, total=total, params=params),
    )


@me_router.get("/summary", response_model=SuccessResponse[EarningSummaryRead])
def my_earnings_summary(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    query: Annotated[EarningListQuery, Query()],
) -> SuccessResponse[EarningSummaryRead]:
    summary = EarningService(db).summary_mine(current_user, query)
    return SuccessResponse(message=EarningMessages.SUMMARY_RETRIEVED, data=summary)


@business_router.get("", response_model=SuccessResponse[Page[EarningRead]])
def list_business_earnings(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[EarningListQuery, Query()],
) -> SuccessResponse[Page[EarningRead]]:
    items, total = EarningService(db).list_for_business(business_id, current_user, query, params)
    return SuccessResponse(
        message=EarningMessages.LIST_RETRIEVED,
        data=Page[EarningRead].create(items=items, total=total, params=params),
    )


@business_router.get("/summary", response_model=SuccessResponse[EarningSummaryRead])
def business_earnings_summary(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    query: Annotated[EarningListQuery, Query()],
) -> SuccessResponse[EarningSummaryRead]:
    summary = EarningService(db).summary_for_business(business_id, current_user, query)
    return SuccessResponse(message=EarningMessages.SUMMARY_RETRIEVED, data=summary)


@admin_router.get("", response_model=SuccessResponse[Page[EarningRead]])
def list_all_earnings(
    db: DbSessionDep,
    _admin: EarningViewAnyDep,
    params: PaginationDep,
    query: Annotated[AdminEarningListQuery, Query()],
) -> SuccessResponse[Page[EarningRead]]:
    items, total = EarningService(db).list_all(query, params)
    return SuccessResponse(
        message=EarningMessages.LIST_RETRIEVED,
        data=Page[EarningRead].create(items=items, total=total, params=params),
    )


@admin_router.get("/summary", response_model=SuccessResponse[EarningSummaryRead])
def all_earnings_summary(
    db: DbSessionDep,
    _admin: EarningViewAnyDep,
    query: Annotated[AdminEarningListQuery, Query()],
) -> SuccessResponse[EarningSummaryRead]:
    summary = EarningService(db).summary_all(query)
    return SuccessResponse(message=EarningMessages.SUMMARY_RETRIEVED, data=summary)


router = APIRouter()
router.include_router(me_router)
router.include_router(business_router)
router.include_router(admin_router)
