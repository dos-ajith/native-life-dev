from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import CommunityTimelineMessages
from app.core.openapi_tags import ApiTag
from app.schemas.community_timeline import (
    DEFAULT_TIMELINE_LIMIT,
    MAX_TIMELINE_LIMIT,
    CommunityTimelineRead,
)
from app.schemas.response import SuccessResponse
from app.services.community_timeline_service import CommunityTimelineService

router = APIRouter(prefix="/communities/{community_id}/timeline", tags=[ApiTag.COMMUNITY_TIMELINE])


@router.get("", response_model=SuccessResponse[CommunityTimelineRead])
def get_timeline(
    community_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    before: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_TIMELINE_LIMIT)] = DEFAULT_TIMELINE_LIMIT,
) -> SuccessResponse[CommunityTimelineRead]:
    timeline = CommunityTimelineService(db).page(community_id, current_user, before, limit)
    return SuccessResponse(message=CommunityTimelineMessages.RETRIEVED, data=timeline)
