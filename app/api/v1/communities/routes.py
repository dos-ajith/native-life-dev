from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, SettingsDep
from app.core.messages import CommunityMessages
from app.core.openapi_tags import ApiTag
from app.models.community_member import CommunityMemberStatus
from app.models.user import User
from app.schemas.community import (
    CommunityCreate,
    CommunityMemberRead,
    CommunityPostRemove,
    CommunityRead,
    CommunityUpdate,
    RecommendedCommunityRead,
)
from app.schemas.pagination import Page
from app.schemas.post import PostDetailRead
from app.schemas.response import SuccessResponse
from app.services.community_membership_service import CommunityMembershipService
from app.services.community_post_moderation_service import CommunityPostModerationService
from app.services.community_read_service import CommunityReadService
from app.services.community_service import CommunityService
from app.services.post_service import PostService

MIN_SEARCH_LENGTH = 2
MAX_SEARCH_LENGTH = 100

router = APIRouter(prefix="/communities")


def _read(db: Session, community_id: UUID, viewer: User) -> CommunityRead:
    return CommunityService(db).get_for_viewer(community_id, viewer)


@router.post(
    "",
    tags=[ApiTag.COMMUNITY],
    response_model=SuccessResponse[CommunityRead],
    status_code=status.HTTP_201_CREATED,
)
def create_community(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    auto_approve_members: Annotated[bool, Form()] = False,
    max_members: Annotated[int | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[CommunityRead]:
    payload = CommunityCreate(
        name=name,
        description=description,
        auto_approve_members=auto_approve_members,
        max_members=max_members,
    )
    community = CommunityService(db).create(payload, current_user, image, settings.upload_dir)
    return SuccessResponse(
        message=CommunityMessages.CREATED,
        data=CommunityRead.from_community(community, current_user.id),
    )


@router.get("", tags=[ApiTag.COMMUNITY], response_model=SuccessResponse[Page[CommunityRead]])
def search_communities(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    q: Annotated[
        str | None, Query(min_length=MIN_SEARCH_LENGTH, max_length=MAX_SEARCH_LENGTH)
    ] = None,
) -> SuccessResponse[Page[CommunityRead]]:
    term = q.strip() if q is not None else None
    items, total = CommunityService(db).search(term or None, params, current_user)
    page = Page[CommunityRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CommunityMessages.LIST_RETRIEVED, data=page)


@router.get("/mine", tags=[ApiTag.COMMUNITY], response_model=SuccessResponse[Page[CommunityRead]])
def list_my_communities(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[CommunityRead]]:
    items, total = CommunityService(db).list_mine(params, current_user)
    page = Page[CommunityRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CommunityMessages.MINE_RETRIEVED, data=page)


@router.get(
    "/recommended",
    tags=[ApiTag.COMMUNITY],
    response_model=SuccessResponse[Page[RecommendedCommunityRead]],
)
def list_recommended_communities(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[RecommendedCommunityRead]]:
    items, total = CommunityService(db).list_recommended(params, current_user)
    page = Page[RecommendedCommunityRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CommunityMessages.RECOMMENDED_RETRIEVED, data=page)


@router.get(
    "/{community_id}", tags=[ApiTag.COMMUNITY], response_model=SuccessResponse[CommunityRead]
)
def get_community(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityRead]:
    return SuccessResponse(
        message=CommunityMessages.RETRIEVED, data=_read(db, community_id, current_user)
    )


@router.patch(
    "/{community_id}", tags=[ApiTag.COMMUNITY], response_model=SuccessResponse[CommunityRead]
)
def update_community(
    community_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    auto_approve_members: Annotated[bool | None, Form()] = None,
    max_members: Annotated[int | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[CommunityRead]:
    provided = {
        "name": name,
        "description": description,
        "auto_approve_members": auto_approve_members,
        "max_members": max_members,
    }
    payload = CommunityUpdate(
        **{key: value for key, value in provided.items() if value is not None}
    )
    CommunityService(db).update(community_id, payload, current_user, image, settings.upload_dir)
    return SuccessResponse(
        message=CommunityMessages.UPDATED, data=_read(db, community_id, current_user)
    )


@router.post(
    "/{community_id}/join",
    tags=[ApiTag.COMMUNITY_MEMBERSHIP],
    response_model=SuccessResponse[CommunityRead],
)
def join_community(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityRead]:
    member = CommunityMembershipService(db).join(community_id, current_user)
    message = (
        CommunityMessages.JOINED
        if member.status == CommunityMemberStatus.ACTIVE
        else CommunityMessages.JOIN_REQUESTED
    )
    return SuccessResponse(message=message, data=_read(db, community_id, current_user))


@router.delete(
    "/{community_id}/leave",
    tags=[ApiTag.COMMUNITY_MEMBERSHIP],
    response_model=SuccessResponse[CommunityRead],
)
def leave_community(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityRead]:
    previous = CommunityMembershipService(db).leave(community_id, current_user)
    message = (
        CommunityMessages.LEFT
        if previous == CommunityMemberStatus.ACTIVE
        else CommunityMessages.JOIN_REQUEST_CANCELLED
    )
    return SuccessResponse(message=message, data=_read(db, community_id, current_user))


@router.post(
    "/{community_id}/read",
    tags=[ApiTag.COMMUNITY_TIMELINE],
    response_model=SuccessResponse[CommunityRead],
)
def mark_community_read(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityRead]:
    CommunityReadService(db).mark_read(community_id, current_user)
    return SuccessResponse(
        message=CommunityMessages.MARKED_READ, data=_read(db, community_id, current_user)
    )


@router.get(
    "/{community_id}/members",
    tags=[ApiTag.COMMUNITY_MEMBERSHIP],
    response_model=SuccessResponse[Page[CommunityMemberRead]],
)
def list_members(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[CommunityMemberRead]]:
    members, total = CommunityMembershipService(db).list_members(community_id, current_user, params)
    page = Page[CommunityMemberRead].create(
        items=[CommunityMemberRead.from_member(item) for item in members],
        total=total,
        params=params,
    )
    return SuccessResponse(message=CommunityMessages.MEMBERS_RETRIEVED, data=page)


@router.get(
    "/{community_id}/requests",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[Page[CommunityMemberRead]],
)
def list_join_requests(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[CommunityMemberRead]]:
    members, total = CommunityMembershipService(db).list_requests(
        community_id, current_user, params
    )
    page = Page[CommunityMemberRead].create(
        items=[CommunityMemberRead.from_member(item) for item in members],
        total=total,
        params=params,
    )
    return SuccessResponse(message=CommunityMessages.REQUESTS_RETRIEVED, data=page)


@router.post(
    "/{community_id}/requests/{user_id}/approve",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[CommunityMemberRead],
)
def approve_join_request(
    community_id: UUID, user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CommunityMemberRead]:
    member = CommunityMembershipService(db).approve_request(community_id, user_id, current_user)
    return SuccessResponse(
        message=CommunityMessages.REQUEST_APPROVED, data=CommunityMemberRead.from_member(member)
    )


@router.post(
    "/{community_id}/requests/{user_id}/reject",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[None],
)
def reject_join_request(
    community_id: UUID, user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CommunityMembershipService(db).reject_request(community_id, user_id, current_user)
    return SuccessResponse(message=CommunityMessages.REQUEST_REJECTED, data=None)


@router.delete(
    "/{community_id}/members/{user_id}",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[None],
)
def remove_member(
    community_id: UUID, user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CommunityMembershipService(db).remove_member(community_id, user_id, current_user)
    return SuccessResponse(message=CommunityMessages.MEMBER_REMOVED, data=None)


@router.get(
    "/{community_id}/blocked",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[Page[CommunityMemberRead]],
)
def list_blocked_members(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[CommunityMemberRead]]:
    members, total = CommunityMembershipService(db).list_blocked(community_id, current_user, params)
    page = Page[CommunityMemberRead].create(
        items=[CommunityMemberRead.from_member(item) for item in members],
        total=total,
        params=params,
    )
    return SuccessResponse(message=CommunityMessages.MEMBERS_RETRIEVED, data=page)


@router.post(
    "/{community_id}/blocked/{user_id}",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[None],
)
def block_member(
    community_id: UUID, user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CommunityMembershipService(db).block_member(community_id, user_id, current_user)
    return SuccessResponse(message=CommunityMessages.MEMBER_BLOCKED, data=None)


@router.delete(
    "/{community_id}/blocked/{user_id}",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[None],
)
def unblock_member(
    community_id: UUID, user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CommunityMembershipService(db).unblock_member(community_id, user_id, current_user)
    return SuccessResponse(message=CommunityMessages.MEMBER_UNBLOCKED, data=None)


@router.get(
    "/{community_id}/posts",
    tags=[ApiTag.COMMUNITY_POSTS],
    response_model=SuccessResponse[Page[PostDetailRead]],
)
def list_community_posts(
    community_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[PostDetailRead]]:
    items, total = PostService(db).list_community_posts_with_details(
        community_id, params, current_user
    )
    page = Page[PostDetailRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CommunityMessages.POSTS_RETRIEVED, data=page)


@router.delete(
    "/{community_id}/posts/{post_id}",
    tags=[ApiTag.COMMUNITY_MODERATION],
    response_model=SuccessResponse[None],
)
def remove_community_post(
    community_id: UUID,
    post_id: UUID,
    payload: CommunityPostRemove,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[None]:
    CommunityPostModerationService(db).remove_post(
        community_id, post_id, current_user, payload.reason
    )
    return SuccessResponse(message=CommunityMessages.POST_REMOVED, data=None)
