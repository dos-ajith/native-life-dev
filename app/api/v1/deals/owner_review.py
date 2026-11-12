from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.schemas.deal import DealListQuery, DealRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.deal_owner_review_service import DealOwnerReviewService

router = APIRouter(prefix="/deals", tags=[ApiTag.DEAL_OWNER_REVIEW])
me_router = APIRouter(prefix="/me/deals", tags=[ApiTag.DEAL_OWNER_REVIEW])


@me_router.get("/on-my-businesses", response_model=SuccessResponse[Page[DealRead]])
def list_deals_on_my_businesses(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[DealListQuery, Query()],
) -> SuccessResponse[Page[DealRead]]:
    deals, total = DealOwnerReviewService(db).list_for_my_businesses(
        current_user, query.status, params
    )
    return SuccessResponse(
        message=DealMessages.LIST_RETRIEVED,
        data=Page[DealRead].create(items=deals, total=total, params=params),
    )


@router.post("/{deal_id}/block", response_model=SuccessResponse[DealRead])
def block_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealOwnerReviewService(db).block(deal_id, current_user)
    return SuccessResponse(message=DealMessages.BLOCKED_BY_OWNER, data=deal)


@router.post("/{deal_id}/request-republish", response_model=SuccessResponse[DealRead])
def request_deal_republish(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealOwnerReviewService(db).request_republish(deal_id, current_user)
    return SuccessResponse(message=DealMessages.REPUBLISH_REQUESTED, data=deal)


@router.post("/{deal_id}/approve-republish", response_model=SuccessResponse[DealRead])
def approve_deal_republish(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealOwnerReviewService(db).approve_republish(deal_id, current_user)
    return SuccessResponse(message=DealMessages.REPUBLISH_APPROVED, data=deal)


@router.post("/{deal_id}/reject-republish", response_model=SuccessResponse[DealRead])
def reject_deal_republish(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealOwnerReviewService(db).reject_republish(deal_id, current_user)
    return SuccessResponse(message=DealMessages.REPUBLISH_REJECTED, data=deal)
