from typing import Annotated

from fastapi import Depends

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from app.models.user import User

CategorySuggestDep = Annotated[User, Depends(require_permission(PermissionName.CATEGORY_SUGGEST))]
CategoryViewPendingDep = Annotated[
    User, Depends(require_permission(PermissionName.CATEGORY_VIEW_PENDING))
]
CategoryApproveDep = Annotated[User, Depends(require_permission(PermissionName.CATEGORY_APPROVE))]
CategoryRejectDep = Annotated[User, Depends(require_permission(PermissionName.CATEGORY_REJECT))]
CategoryCreateDep = Annotated[User, Depends(require_permission(PermissionName.CATEGORY_CREATE))]
CategoryUpdateDep = Annotated[User, Depends(require_permission(PermissionName.CATEGORY_UPDATE))]
CategoryDeleteDep = Annotated[User, Depends(require_permission(PermissionName.CATEGORY_DELETE))]
