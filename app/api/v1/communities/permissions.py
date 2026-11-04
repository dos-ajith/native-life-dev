from typing import Annotated

from fastapi import Depends

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from app.models.user import User

CommunityViewPendingDep = Annotated[
    User, Depends(require_permission(PermissionName.COMMUNITY_VIEW_PENDING))
]
CommunityApproveDep = Annotated[User, Depends(require_permission(PermissionName.COMMUNITY_APPROVE))]
CommunityRejectDep = Annotated[User, Depends(require_permission(PermissionName.COMMUNITY_REJECT))]
