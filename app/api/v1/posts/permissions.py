from typing import Annotated

from fastapi import Depends

from app.api.deps import require_permission, require_permission_or_guest
from app.core.permissions import PermissionName
from app.models.user import User

PostViewDep = Annotated[
    User | None, Depends(require_permission_or_guest(PermissionName.POST_VIEW))
]
PostCreateDep = Annotated[User, Depends(require_permission(PermissionName.POST_CREATE))]
PostLikeDep = Annotated[User, Depends(require_permission(PermissionName.POST_LIKE))]
PostCommentDep = Annotated[User, Depends(require_permission(PermissionName.POST_COMMENT))]
PostShareDep = Annotated[User, Depends(require_permission(PermissionName.POST_SHARE))]
