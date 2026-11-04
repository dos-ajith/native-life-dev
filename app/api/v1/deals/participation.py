from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.schemas.deal import DealRead
from app.schemas.deal_participant import DealParticipantRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.deal_participation_service import DealParticipationService

router = APIRouter(prefix="/deals/{deal_id}", tags=[ApiTag.DEAL_PARTICIPATION])
me_router = APIRouter(prefix="/me/joined-deals", tags=[ApiTag.DEAL_PARTICIPATION])


@me_router.get("", response_model=SuccessResponse[Page[DealRead]])
def list_my_joined_deals(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[DealRead]]:
    deals, total = DealParticipationService(db).list_joined(current_user, params)
    return SuccessResponse(
        message=DealMessages.JOINED_LIST_RETRIEVED,
        data=Page[DealRead].create(items=deals, total=total, params=params),
    )


@router.post("/join", response_model=SuccessResponse[DealRead], status_code=status.HTTP_201_CREATED)
def join_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealParticipationService(db).join(deal_id, current_user)
    return SuccessResponse(message=DealMessages.JOINED, data=deal)


@router.delete("/join", response_model=SuccessResponse[None])
def leave_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    DealParticipationService(db).leave(deal_id, current_user)
    return SuccessResponse(message=DealMessages.LEFT, data=None)


@router.get("/participants", response_model=SuccessResponse[Page[DealParticipantRead]])
def list_deal_participants(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[DealParticipantRead]]:
    participants, total = DealParticipationService(db).list_participants(
        deal_id, current_user, params
    )
    return SuccessResponse(
        message=DealMessages.PARTICIPANTS_RETRIEVED,
        data=Page[DealParticipantRead].create(items=participants, total=total, params=params),
    )
