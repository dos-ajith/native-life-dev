from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import PollMessages
from app.core.openapi_tags import ApiTag
from app.schemas.community_poll import CommunityPollCreate, CommunityPollRead
from app.schemas.pagination import Page
from app.schemas.poll import PollVoteRequest
from app.schemas.response import SuccessResponse
from app.services.community_poll_service import CommunityPollService

router = APIRouter(prefix="/communities/{community_id}/polls", tags=[ApiTag.COMMUNITY_POLLS])


@router.post(
    "", response_model=SuccessResponse[CommunityPollRead], status_code=status.HTTP_201_CREATED
)
def create_poll(
    community_id: UUID,
    payload: CommunityPollCreate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CommunityPollRead]:
    poll = CommunityPollService(db).create(community_id, current_user, payload)
    return SuccessResponse(message=PollMessages.CREATED, data=poll)


@router.get("", response_model=SuccessResponse[Page[CommunityPollRead]])
def list_polls(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[CommunityPollRead]]:
    items, total = CommunityPollService(db).list_polls(community_id, params, current_user)
    page = Page[CommunityPollRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=PollMessages.LIST_RETRIEVED, data=page)


@router.get("/{poll_id}", response_model=SuccessResponse[CommunityPollRead])
def get_poll(
    community_id: UUID, poll_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityPollRead]:
    poll = CommunityPollService(db).get(community_id, poll_id, current_user)
    return SuccessResponse(message=PollMessages.RETRIEVED, data=poll)


@router.put("/{poll_id}/vote", response_model=SuccessResponse[CommunityPollRead])
def vote_in_poll(
    community_id: UUID,
    poll_id: UUID,
    payload: PollVoteRequest,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CommunityPollRead]:
    poll = CommunityPollService(db).vote(community_id, poll_id, current_user, payload.option_ids)
    return SuccessResponse(message=PollMessages.VOTED, data=poll)


@router.delete("/{poll_id}/vote", response_model=SuccessResponse[CommunityPollRead])
def remove_poll_vote(
    community_id: UUID, poll_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityPollRead]:
    poll = CommunityPollService(db).remove_vote(community_id, poll_id, current_user)
    return SuccessResponse(message=PollMessages.VOTE_REMOVED, data=poll)
