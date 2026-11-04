from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.posts.permissions import PostViewRequiredDep
from app.core.messages import UpdateFeedMessages
from app.core.openapi_tags import ApiTag
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.update_feed import UpdateFeedItem, UpdateFeedQuery
from app.services.update_feed_service import UpdateFeedService

router = APIRouter(prefix="/updates", tags=[ApiTag.UPDATES])


@router.get("", response_model=SuccessResponse[Page[UpdateFeedItem]])
def list_updates(
    db: DbSessionDep,
    viewer: PostViewRequiredDep,
    params: PaginationDep,
    query: Annotated[UpdateFeedQuery, Query()],
) -> SuccessResponse[Page[UpdateFeedItem]]:
    items, total = UpdateFeedService(db).list_for(params, viewer, query.village_id)
    return SuccessResponse(
        message=UpdateFeedMessages.LIST_RETRIEVED,
        data=Page[UpdateFeedItem].create(items=items, total=total, params=params),
    )
