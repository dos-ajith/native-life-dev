from typing import Annotated

from fastapi import Depends

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from app.models.user import User

NativePlaceSuggestDep = Annotated[
    User, Depends(require_permission(PermissionName.NATIVE_PLACE_SUGGEST))
]
NativePlaceViewPendingDep = Annotated[
    User, Depends(require_permission(PermissionName.NATIVE_PLACE_VIEW_PENDING))
]
NativePlaceApproveDep = Annotated[
    User, Depends(require_permission(PermissionName.NATIVE_PLACE_APPROVE))
]
NativePlaceRejectDep = Annotated[
    User, Depends(require_permission(PermissionName.NATIVE_PLACE_REJECT))
]
NativePlaceManageDep = Annotated[
    User, Depends(require_permission(PermissionName.NATIVE_PLACE_MANAGE))
]
