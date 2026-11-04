from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form

from app.api.deps import DbSessionDep, PaginationDep, SettingsDep, require_any_permission
from app.core.messages import RoleUpgradeRequestMessages
from app.core.openapi_tags import ApiTag
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.role_upgrade_request import RoleUpgradeRequestRead, RoleUpgradeRequestReject
from app.services.role_upgrade_request_service import RoleUpgradeRequestService

router = APIRouter(prefix="/admin/upgrade-requests", tags=[ApiTag.ADMIN_ROLE_UPGRADE_REVIEW])

RoleUpgradeRequestViewAnyDep = Annotated[
    User,
    Depends(
        require_any_permission(
            PermissionName.ROLE_UPGRADE_REQUEST_VIEW_ANY,
            PermissionName.ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER,
        )
    ),
]
RoleUpgradeRequestApproveDep = Annotated[
    User,
    Depends(
        require_any_permission(
            PermissionName.ROLE_UPGRADE_REQUEST_APPROVE,
            PermissionName.ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER,
        )
    ),
]
RoleUpgradeRequestRejectDep = Annotated[
    User,
    Depends(
        require_any_permission(
            PermissionName.ROLE_UPGRADE_REQUEST_REJECT,
            PermissionName.ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER,
        )
    ),
]


@router.get("", response_model=SuccessResponse[Page[RoleUpgradeRequestRead]])
def list_pending_role_upgrade_requests(
    db: DbSessionDep,
    settings: SettingsDep,
    reviewer: RoleUpgradeRequestViewAnyDep,
    params: PaginationDep,
) -> SuccessResponse[Page[RoleUpgradeRequestRead]]:
    items, total = RoleUpgradeRequestService(db, settings).list_pending(params, reviewer)
    page = Page[RoleUpgradeRequestRead].create(
        items=[RoleUpgradeRequestRead.model_validate(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=RoleUpgradeRequestMessages.LIST_RETRIEVED, data=page)


@router.get("/{request_id}", response_model=SuccessResponse[RoleUpgradeRequestRead])
def get_role_upgrade_request(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    reviewer: RoleUpgradeRequestViewAnyDep,
) -> SuccessResponse[RoleUpgradeRequestRead]:
    request = RoleUpgradeRequestService(db, settings).get_for_admin(request_id, reviewer)
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.RETRIEVED,
        data=RoleUpgradeRequestRead.model_validate(request),
    )


@router.post("/{request_id}/approve", response_model=SuccessResponse[RoleUpgradeRequestRead])
def approve_role_upgrade_request(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    admin: RoleUpgradeRequestApproveDep,
    background_tasks: BackgroundTasks,
    review_note: Annotated[str | None, Form()] = None,
) -> SuccessResponse[RoleUpgradeRequestRead]:
    request = RoleUpgradeRequestService(db, settings).approve(
        request_id, admin, review_note, background_tasks
    )
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.APPROVED,
        data=RoleUpgradeRequestRead.model_validate(request),
    )


@router.post("/{request_id}/reject", response_model=SuccessResponse[RoleUpgradeRequestRead])
def reject_role_upgrade_request(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    admin: RoleUpgradeRequestRejectDep,
    background_tasks: BackgroundTasks,
    review_note: Annotated[str, Form()],
) -> SuccessResponse[RoleUpgradeRequestRead]:
    payload = RoleUpgradeRequestReject(review_note=review_note)
    request = RoleUpgradeRequestService(db, settings).reject(
        request_id, admin, payload.review_note, background_tasks
    )
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.REJECTED,
        data=RoleUpgradeRequestRead.model_validate(request),
    )
