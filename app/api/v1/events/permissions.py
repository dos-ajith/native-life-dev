from typing import Annotated

from fastapi import Depends

from app.api.deps import require_any_permission, require_permission
from app.core.permissions import PermissionName
from app.models.user import User

EventViewDep = Annotated[User, Depends(require_permission(PermissionName.EVENTS_VIEW))]
EventCreateDep = Annotated[User, Depends(require_permission(PermissionName.EVENTS_CREATE))]
EventFeatureDep = Annotated[User, Depends(require_permission(PermissionName.EVENTS_FEATURE))]
EventManageDep = Annotated[
    User,
    Depends(require_any_permission(PermissionName.EVENTS_CREATE, PermissionName.EVENTS_UPDATE_ANY)),
]
EventDeleteDep = Annotated[
    User,
    Depends(require_any_permission(PermissionName.EVENTS_CREATE, PermissionName.EVENTS_DELETE_ANY)),
]
