from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSessionDep, SettingsDep
from app.api.v1.admin.permissions import DashboardAccessDep
from app.core.messages import DashboardMessages
from app.core.openapi_tags import ApiTag
from app.schemas.dashboard import DashboardQuery, DashboardSummaryRead
from app.schemas.response import SuccessResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/admin/dashboard", tags=[ApiTag.ADMIN_DASHBOARD])


@router.get("/summary", response_model=SuccessResponse[DashboardSummaryRead])
def dashboard_summary(
    db: DbSessionDep,
    settings: SettingsDep,
    access: DashboardAccessDep,
    query: Annotated[DashboardQuery, Query()],
) -> SuccessResponse[DashboardSummaryRead]:
    summary = DashboardService(db).summary(query, settings.default_currency, access)
    return SuccessResponse(message=DashboardMessages.SUMMARY_RETRIEVED, data=summary)
