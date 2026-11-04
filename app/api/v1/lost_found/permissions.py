from typing import Annotated

from fastapi import Depends

from app.api.deps import require_any_permission, require_permission
from app.core.permissions import PermissionName
from app.models.user import User

LostFoundViewDep = Annotated[User, Depends(require_permission(PermissionName.LOST_FOUND_VIEW))]
LostFoundCreateDep = Annotated[User, Depends(require_permission(PermissionName.LOST_FOUND_CREATE))]
LostFoundManageDep = Annotated[
    User,
    Depends(
        require_any_permission(
            PermissionName.LOST_FOUND_CREATE, PermissionName.LOST_FOUND_UPDATE_ANY
        )
    ),
]
LostFoundDeleteDep = Annotated[
    User,
    Depends(
        require_any_permission(
            PermissionName.LOST_FOUND_CREATE, PermissionName.LOST_FOUND_DELETE_ANY
        )
    ),
]
