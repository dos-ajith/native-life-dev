from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep, require_permission
from app.core.messages import AccountRoleMessages
from app.core.openapi_tags import ApiTag
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.account_role import AccountRoleRead, SelectableAccountRoleRead
from app.schemas.response import SuccessResponse
from app.schemas.role_upgrade_request import RoleUpgradeRequestRead
from app.services.account_role_service import AccountRoleService
from app.services.account_role_status_service import requires_verification

router = APIRouter(prefix="/account-roles", tags=[ApiTag.ACCOUNT_ROLE])
me_router = APIRouter(prefix="/users/me/account-role", tags=[ApiTag.ACCOUNT_ROLE])

VerificationSubmitDep = Annotated[
    User, Depends(require_permission(PermissionName.ROLE_UPGRADE_REQUEST_CREATE))
]


@router.get("", response_model=SuccessResponse[list[SelectableAccountRoleRead]])
def list_account_roles(
    db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[list[SelectableAccountRoleRead]]:
    roles = AccountRoleService(db, settings).list_selectable()
    return SuccessResponse(
        message=AccountRoleMessages.LIST_RETRIEVED,
        data=[
            SelectableAccountRoleRead(
                id=role.id,
                name=role.name,
                slug=role.slug,
                requires_verification=requires_verification(role.slug),
            )
            for role in roles
        ],
    )


@me_router.get("", response_model=SuccessResponse[AccountRoleRead | None])
def get_my_account_role(
    db: DbSessionDep, settings: SettingsDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[AccountRoleRead | None]:
    account_role = AccountRoleService(db, settings).current(current_user)
    return SuccessResponse(message=AccountRoleMessages.RETRIEVED, data=account_role)


@me_router.put("", response_model=SuccessResponse[AccountRoleRead | None])
def select_my_account_role(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    role_id: Annotated[UUID, Form()],
    document: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[AccountRoleRead | None]:
    selection = AccountRoleService(db, settings).select(current_user, role_id, document)
    return SuccessResponse(message=AccountRoleMessages.SELECTED, data=selection.account_role)


@me_router.post(
    "/verification",
    response_model=SuccessResponse[RoleUpgradeRequestRead],
    status_code=status.HTTP_201_CREATED,
)
def submit_my_account_role_verification(
    db: DbSessionDep,
    settings: SettingsDep,
    actor: VerificationSubmitDep,
    document: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[RoleUpgradeRequestRead]:
    request = AccountRoleService(db, settings).submit_verification(actor, document)
    return SuccessResponse(
        message=AccountRoleMessages.VERIFICATION_SUBMITTED,
        data=RoleUpgradeRequestRead.model_validate(request),
    )
