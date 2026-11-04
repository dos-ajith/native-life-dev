from typing import Annotated

from fastapi import Depends

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from app.models.user import User

BusinessSearchDep = Annotated[User, Depends(require_permission(PermissionName.BUSINESS_SEARCH))]
BusinessEscalateDep = Annotated[User, Depends(require_permission(PermissionName.BUSINESS_ESCALATE))]
BusinessCreateAnyDep = Annotated[
    User, Depends(require_permission(PermissionName.BUSINESS_CREATE_ANY))
]
BusinessReviewDep = Annotated[User, Depends(require_permission(PermissionName.BUSINESS_REVIEW))]
