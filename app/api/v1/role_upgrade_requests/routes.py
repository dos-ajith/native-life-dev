from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import (
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    SettingsDep,
    require_permission,
)
from app.core.messages import RoleUpgradeRequestMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.role import RoleSummary
from app.schemas.role_upgrade_request import (
    RoleUpgradeRequestCreate,
    RoleUpgradeRequestDocumentRead,
    RoleUpgradeRequestRead,
)
from app.services.role_upgrade_request_service import RoleUpgradeRequestService

router = APIRouter(prefix="/upgrade-requests", tags=["upgrade-requests"])

RoleUpgradeRequestCreateDep = Annotated[
    User, Depends(require_permission(PermissionName.ROLE_UPGRADE_REQUEST_CREATE))
]
RoleUpgradeRequestViewOwnDep = Annotated[
    User, Depends(require_permission(PermissionName.ROLE_UPGRADE_REQUEST_VIEW_OWN))
]


@router.post(
    "", response_model=SuccessResponse[RoleUpgradeRequestRead], status_code=status.HTTP_201_CREATED
)
def submit_role_upgrade_request(
    db: DbSessionDep,
    settings: SettingsDep,
    actor: RoleUpgradeRequestCreateDep,
    requested_role_id: Annotated[UUID, Form()],
    reason: Annotated[str | None, Form()] = None,
    document: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[RoleUpgradeRequestRead]:
    payload = RoleUpgradeRequestCreate(requested_role_id=requested_role_id, reason=reason)
    request = RoleUpgradeRequestService(db, settings).submit(
        actor, payload.requested_role_id, payload.reason, document
    )
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.SUBMITTED,
        data=RoleUpgradeRequestRead.model_validate(request),
    )


@router.get("/roles", response_model=SuccessResponse[list[RoleSummary]])
def list_requestable_roles(
    db: DbSessionDep, settings: SettingsDep, actor: RoleUpgradeRequestCreateDep
) -> SuccessResponse[list[RoleSummary]]:
    roles = RoleUpgradeRequestService(db, settings).list_requestable_roles(actor)
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.REQUESTABLE_ROLES_RETRIEVED,
        data=[RoleSummary.model_validate(role) for role in roles],
    )


@router.get("", response_model=SuccessResponse[Page[RoleUpgradeRequestRead]])
def list_own_role_upgrade_requests(
    db: DbSessionDep,
    settings: SettingsDep,
    actor: RoleUpgradeRequestViewOwnDep,
    params: PaginationDep,
) -> SuccessResponse[Page[RoleUpgradeRequestRead]]:
    items, total = RoleUpgradeRequestService(db, settings).list_own(actor, params)
    page = Page[RoleUpgradeRequestRead].create(
        items=[RoleUpgradeRequestRead.model_validate(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=RoleUpgradeRequestMessages.LIST_RETRIEVED, data=page)


@router.get("/{request_id}", response_model=SuccessResponse[RoleUpgradeRequestRead])
def get_own_role_upgrade_request(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    actor: RoleUpgradeRequestViewOwnDep,
) -> SuccessResponse[RoleUpgradeRequestRead]:
    request = RoleUpgradeRequestService(db, settings).get_own(actor, request_id)
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.RETRIEVED,
        data=RoleUpgradeRequestRead.model_validate(request),
    )


@router.post(
    "/{request_id}/documents",
    response_model=SuccessResponse[RoleUpgradeRequestDocumentRead],
    status_code=status.HTTP_201_CREATED,
)
def add_role_upgrade_request_document(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    actor: RoleUpgradeRequestCreateDep,
    document: Annotated[UploadFile, File()],
) -> SuccessResponse[RoleUpgradeRequestDocumentRead]:
    doc = RoleUpgradeRequestService(db, settings).add_document(actor, request_id, document)
    return SuccessResponse(
        message=RoleUpgradeRequestMessages.DOCUMENT_ADDED,
        data=RoleUpgradeRequestDocumentRead.model_validate(doc),
    )


@router.get("/{request_id}/documents/{document_id}")
def download_role_upgrade_request_document(
    request_id: UUID,
    document_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    actor: CurrentActiveUserDep,
) -> FileResponse:
    document = RoleUpgradeRequestService(db, settings).get_document_for_download(
        actor, request_id, document_id
    )
    return FileResponse(
        path=document.storage_path,
        media_type=document.content_type,
        filename=document.file_name,
    )
