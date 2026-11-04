from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.communities.permissions import (
    CommunityApproveDep,
    CommunityRejectDep,
    CommunityViewPendingDep,
)
from app.core.messages import CommunityMessages
from app.core.openapi_tags import ApiTag
from app.schemas.community import CommunityRead, CommunityReject
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.community_service import CommunityService

router = APIRouter(prefix="/admin/communities", tags=[ApiTag.ADMIN_COMMUNITY_REVIEW])


@router.get("/pending", response_model=SuccessResponse[Page[CommunityRead]])
def list_pending_communities(
    db: DbSessionDep, reviewer: CommunityViewPendingDep, params: PaginationDep
) -> SuccessResponse[Page[CommunityRead]]:
    items, total = CommunityService(db).list_pending(params, reviewer)
    page = Page[CommunityRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CommunityMessages.PENDING_LIST_RETRIEVED, data=page)


@router.post("/{community_id}/approve", response_model=SuccessResponse[CommunityRead])
def approve_community(
    community_id: UUID, db: DbSessionDep, admin: CommunityApproveDep
) -> SuccessResponse[CommunityRead]:
    community = CommunityService(db).approve(community_id, admin)
    return SuccessResponse(
        message=CommunityMessages.APPROVED,
        data=CommunityRead.from_community(community, admin.id),
    )


@router.post("/{community_id}/reject", response_model=SuccessResponse[CommunityRead])
def reject_community(
    community_id: UUID, payload: CommunityReject, db: DbSessionDep, admin: CommunityRejectDep
) -> SuccessResponse[CommunityRead]:
    community = CommunityService(db).reject(community_id, admin, payload.review_note)
    return SuccessResponse(
        message=CommunityMessages.REJECTED,
        data=CommunityRead.from_community(community, admin.id),
    )
