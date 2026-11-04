from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import CommunityChatMessages
from app.core.openapi_tags import ApiTag
from app.schemas.community_message import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    CommunityMessageCreate,
    CommunityMessageHistory,
    CommunityMessageRead,
)
from app.schemas.response import SuccessResponse
from app.services.community_chat_service import CommunityChatService

router = APIRouter(prefix="/communities/{community_id}/messages", tags=[ApiTag.COMMUNITY_CHAT])


@router.post(
    "", response_model=SuccessResponse[CommunityMessageRead], status_code=status.HTTP_201_CREATED
)
def send_message(
    community_id: UUID,
    payload: CommunityMessageCreate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CommunityMessageRead]:
    message = CommunityChatService(db).send(
        community_id, current_user, payload.content, payload.reply_to_id
    )
    return SuccessResponse(
        message=CommunityChatMessages.SENT, data=CommunityMessageRead.from_message(message)
    )


@router.get("", response_model=SuccessResponse[CommunityMessageHistory])
def list_messages(
    community_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    before_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_HISTORY_LIMIT)] = DEFAULT_HISTORY_LIMIT,
) -> SuccessResponse[CommunityMessageHistory]:
    messages, has_more = CommunityChatService(db).history(
        community_id, current_user, before_id, limit
    )
    return SuccessResponse(
        message=CommunityChatMessages.HISTORY_RETRIEVED,
        data=CommunityMessageHistory(
            items=[CommunityMessageRead.from_message(item) for item in messages],
            has_more=has_more,
            next_before_id=messages[-1].id if has_more and messages else None,
        ),
    )


@router.delete("/{message_id}", response_model=SuccessResponse[None])
def delete_message(
    community_id: UUID, message_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CommunityChatService(db).delete(community_id, message_id, current_user)
    return SuccessResponse(message=CommunityChatMessages.DELETED, data=None)
