from typing import Annotated

from fastapi import Depends

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from app.models.user import User

PopularPlaceManageDep = Annotated[
    User, Depends(require_permission(PermissionName.POPULAR_PLACE_MANAGE))
]
