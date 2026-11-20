from typing import Annotated

from fastapi import Depends

from app.api.deps import require_any_permission, require_permission
from app.core.permissions import DASHBOARD_PERMISSIONS, PermissionName
from app.models.user import User
from app.services.dashboard_service import DashboardAccess


def get_dashboard_access(
    user: Annotated[User, Depends(require_any_permission(*DASHBOARD_PERMISSIONS))],
) -> DashboardAccess:
    return DashboardAccess.for_user(user)


DashboardAccessDep = Annotated[DashboardAccess, Depends(get_dashboard_access)]
ActivityLogViewDep = Annotated[User, Depends(require_permission(PermissionName.ACTIVITY_LOG_VIEW))]
