from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import UserFollowMessages
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.user import UserSummaryRead
from app.schemas.user_follow import FollowCountsRead, FollowStatusRead
from app.services.user_follow_service import UserFollowService

router = APIRouter(prefix="/users", tags=["user-follows"])


@router.post(
    "/{user_id}/follow", response_model=SuccessResponse[None], status_code=status.HTTP_201_CREATED
)
def follow_user(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    UserFollowService(db).follow(user_id, current_user)
    return SuccessResponse(message=UserFollowMessages.FOLLOWED, data=None)


@router.delete("/{user_id}/follow", response_model=SuccessResponse[None])
def unfollow_user(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    UserFollowService(db).unfollow(user_id, current_user)
    return SuccessResponse(message=UserFollowMessages.UNFOLLOWED, data=None)


@router.get("/{user_id}/follow", response_model=SuccessResponse[FollowStatusRead])
def get_follow_status(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[FollowStatusRead]:
    is_following = UserFollowService(db).status(user_id, current_user)
    return SuccessResponse(
        message=UserFollowMessages.STATUS_RETRIEVED,
        data=FollowStatusRead(is_following=is_following),
    )


@router.get("/{user_id}/followers", response_model=SuccessResponse[Page[UserSummaryRead]])
def list_followers(
    user_id: UUID, db: DbSessionDep, _: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[UserSummaryRead]]:
    users, total = UserFollowService(db).list_followers(user_id, params)
    items = [UserSummaryRead.model_validate(user) for user in users]
    page = Page[UserSummaryRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=UserFollowMessages.FOLLOWERS_RETRIEVED, data=page)


@router.get("/{user_id}/following", response_model=SuccessResponse[Page[UserSummaryRead]])
def list_following(
    user_id: UUID, db: DbSessionDep, _: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[UserSummaryRead]]:
    users, total = UserFollowService(db).list_following(user_id, params)
    items = [UserSummaryRead.model_validate(user) for user in users]
    page = Page[UserSummaryRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=UserFollowMessages.FOLLOWING_RETRIEVED, data=page)


@router.get("/{user_id}/follow-counts", response_model=SuccessResponse[FollowCountsRead])
def get_follow_counts(
    user_id: UUID, db: DbSessionDep, _: CurrentActiveUserDep
) -> SuccessResponse[FollowCountsRead]:
    counts = UserFollowService(db).counts(user_id)
    return SuccessResponse(message=UserFollowMessages.COUNTS_RETRIEVED, data=counts)
