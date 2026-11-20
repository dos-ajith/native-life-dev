from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.admin.permissions import ActivityLogViewDep
from app.core.messages import ActivityLogMessages
from app.core.openapi_tags import ApiTag
from app.schemas.activity_log import ActivityLogQuery, ActivityLogRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.activity_log_service import ActivityLogService

router = APIRouter(prefix="/admin/activity-logs", tags=[ApiTag.ADMIN_ACTIVITY_LOGS])


@router.get("", response_model=SuccessResponse[Page[ActivityLogRead]])
def list_activity_logs(
    db: DbSessionDep,
    _viewer: ActivityLogViewDep,
    params: PaginationDep,
    query: Annotated[ActivityLogQuery, Query()],
) -> SuccessResponse[Page[ActivityLogRead]]:
    items, total = ActivityLogService(db).list(query, params)
    return SuccessResponse(
        message=ActivityLogMessages.LIST_RETRIEVED,
        data=Page[ActivityLogRead].create(items=items, total=total, params=params),
    )
