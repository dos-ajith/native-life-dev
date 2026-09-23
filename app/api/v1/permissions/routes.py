from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, status

from app.api.deps import DbSessionDep, PaginationDep, require_permission
from app.core.messages import PermissionMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.permission import PermissionCreate, PermissionRead, PermissionUpdate
from app.schemas.response import SuccessResponse
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/admin/permissions", tags=["permissions"])

PermissionCreateDep = Annotated[User, Depends(require_permission(PermissionName.PERMISSION_CREATE))]
PermissionViewDep = Annotated[User, Depends(require_permission(PermissionName.PERMISSION_VIEW))]
PermissionUpdateDep = Annotated[User, Depends(require_permission(PermissionName.PERMISSION_UPDATE))]
PermissionDeleteDep = Annotated[User, Depends(require_permission(PermissionName.PERMISSION_DELETE))]


@router.post(
    "/create", response_model=SuccessResponse[PermissionRead], status_code=status.HTTP_201_CREATED
)
def create_permission(
    db: DbSessionDep,
    _: PermissionCreateDep,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
) -> SuccessResponse[PermissionRead]:
    payload = PermissionCreate(name=name, description=description)
    permission = PermissionService(db).create(payload)
    return SuccessResponse(
        message=PermissionMessages.CREATED, data=PermissionRead.model_validate(permission)
    )


@router.get("", response_model=SuccessResponse[Page[PermissionRead]])
def list_permissions(
    db: DbSessionDep, _: PermissionViewDep, params: PaginationDep
) -> SuccessResponse[Page[PermissionRead]]:
    items, total = PermissionService(db).list(params)
    page = Page[PermissionRead].create(
        items=[PermissionRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=PermissionMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{permission_id}", response_model=SuccessResponse[PermissionRead])
def edit_permission(
    permission_id: UUID, db: DbSessionDep, _: PermissionViewDep
) -> SuccessResponse[PermissionRead]:
    permission = PermissionService(db).get(permission_id)
    return SuccessResponse(
        message=PermissionMessages.RETRIEVED, data=PermissionRead.model_validate(permission)
    )


@router.patch("/update/{permission_id}", response_model=SuccessResponse[PermissionRead])
def update_permission(
    permission_id: UUID,
    db: DbSessionDep,
    _: PermissionUpdateDep,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
) -> SuccessResponse[PermissionRead]:
    payload = PermissionUpdate(name=name, description=description)
    permission = PermissionService(db).update(permission_id, payload)
    return SuccessResponse(
        message=PermissionMessages.UPDATED, data=PermissionRead.model_validate(permission)
    )


@router.delete("/delete/{permission_id}", response_model=SuccessResponse[None])
def delete_permission(
    permission_id: UUID, db: DbSessionDep, _: PermissionDeleteDep
) -> SuccessResponse[None]:
    PermissionService(db).delete(permission_id)
    return SuccessResponse(message=PermissionMessages.DELETED, data=None)
