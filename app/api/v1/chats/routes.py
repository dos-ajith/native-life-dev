from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import DirectChatMessages, PresenceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.community_message import DEFAULT_HISTORY_LIMIT, MAX_HISTORY_LIMIT
from app.schemas.direct_message import (
    ConversationRead,
    DirectMessageCreate,
    DirectMessageHistory,
    DirectMessageRead,
)
from app.schemas.pagination import Page
from app.schemas.presence import PresenceRead
from app.schemas.response import SuccessResponse
from app.services.direct_chat_service import DirectChatService
from app.services.presence_service import PresenceService

router = APIRouter(prefix="/chats", tags=[ApiTag.CHAT_MESSAGES])


@router.get("", response_model=SuccessResponse[Page[ConversationRead]])
def list_conversations(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[ConversationRead]]:
    items, total = DirectChatService(db).list_conversations(current_user, params)
    page = Page[ConversationRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=DirectChatMessages.CONVERSATIONS_RETRIEVED, data=page)


@router.post(
    "/{user_id}/messages",
    response_model=SuccessResponse[DirectMessageRead],
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    user_id: UUID,
    payload: DirectMessageCreate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[DirectMessageRead]:
    message = DirectChatService(db).send(user_id, current_user, payload.content)
    return SuccessResponse(
        message=DirectChatMessages.SENT, data=DirectMessageRead.from_message(message)
    )


@router.get("/{user_id}/messages", response_model=SuccessResponse[DirectMessageHistory])
def list_messages(
    user_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    before_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_HISTORY_LIMIT)] = DEFAULT_HISTORY_LIMIT,
) -> SuccessResponse[DirectMessageHistory]:
    messages, has_more = DirectChatService(db).history(user_id, current_user, before_id, limit)
    return SuccessResponse(
        message=DirectChatMessages.HISTORY_RETRIEVED,
        data=DirectMessageHistory(
            items=[DirectMessageRead.from_message(item) for item in messages],
            has_more=has_more,
            next_before_id=messages[-1].id if has_more and messages else None,
        ),
    )


@router.post("/{user_id}/read", response_model=SuccessResponse[None])
def mark_read(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    DirectChatService(db).mark_read(user_id, current_user)
    return SuccessResponse(message=DirectChatMessages.MARKED_READ, data=None)


@router.get("/{user_id}/presence", response_model=SuccessResponse[PresenceRead])
def get_presence(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PresenceRead]:
    presence = PresenceService(db).get(current_user, user_id)
    return SuccessResponse(message=PresenceMessages.RETRIEVED, data=presence)
