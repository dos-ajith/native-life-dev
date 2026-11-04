from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import UserBlockMessages
from app.core.openapi_tags import ApiTag
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.user import UserSummaryRead
from app.services.user_block_service import UserBlockService

router = APIRouter(prefix="/users", tags=[ApiTag.CHAT_BLOCKED_USERS])
me_router = APIRouter(prefix="/me", tags=[ApiTag.CHAT_BLOCKED_USERS])


@router.post(
    "/{user_id}/block", response_model=SuccessResponse[None], status_code=status.HTTP_201_CREATED
)
def block_user(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    UserBlockService(db).block(user_id, current_user)
    return SuccessResponse(message=UserBlockMessages.BLOCKED, data=None)


@router.delete("/{user_id}/block", response_model=SuccessResponse[None])
def unblock_user(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    UserBlockService(db).unblock(user_id, current_user)
    return SuccessResponse(message=UserBlockMessages.UNBLOCKED, data=None)


@me_router.get("/blocked-users", response_model=SuccessResponse[Page[UserSummaryRead]])
def list_blocked_users(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[UserSummaryRead]]:
    users, total = UserBlockService(db).list_blocked(current_user, params)
    items = [UserSummaryRead.model_validate(user) for user in users]
    page = Page[UserSummaryRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=UserBlockMessages.LIST_RETRIEVED, data=page)
