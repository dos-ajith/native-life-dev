from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.api.v1.deals.permissions import DealAcceptorDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.schemas.deal import DealInvitationRead, DealRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.deal_acceptance_service import DealAcceptanceService

router = APIRouter(prefix="/deals", tags=[ApiTag.DEAL_ACCEPTANCE])
me_router = APIRouter(prefix="/me/deal-invitations", tags=[ApiTag.DEAL_ACCEPTANCE])


@me_router.get("", response_model=SuccessResponse[Page[DealInvitationRead]])
def list_my_deal_invitations(
    db: DbSessionDep, current_user: DealAcceptorDep, params: PaginationDep
) -> SuccessResponse[Page[DealInvitationRead]]:
    invitations, total = DealAcceptanceService(db).list_open(current_user, params)
    return SuccessResponse(
        message=DealMessages.INVITATIONS_RETRIEVED,
        data=Page[DealInvitationRead].create(items=invitations, total=total, params=params),
    )


@router.post("/{deal_id}/accept", response_model=SuccessResponse[DealRead])
def accept_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealAcceptanceService(db).accept(deal_id, current_user)
    return SuccessResponse(message=DealMessages.ACCEPTED, data=deal)


@router.post("/{deal_id}/decline", response_model=SuccessResponse[None])
def decline_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    DealAcceptanceService(db).decline(deal_id, current_user)
    return SuccessResponse(message=DealMessages.DECLINED, data=None)
