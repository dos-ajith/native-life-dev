from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, status

from app.api.deps import DbSessionDep, PaginationDep, require_permission
from app.core.messages import RoleMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services.role_service import RoleService

router = APIRouter(prefix="/admin/roles", tags=["roles"])

RoleCreateDep = Annotated[User, Depends(require_permission(PermissionName.ROLE_CREATE))]
RoleViewDep = Annotated[User, Depends(require_permission(PermissionName.ROLE_VIEW))]
RoleUpdateDep = Annotated[User, Depends(require_permission(PermissionName.ROLE_UPDATE))]
RoleDeleteDep = Annotated[User, Depends(require_permission(PermissionName.ROLE_DELETE))]


@router.post(
    "/create", response_model=SuccessResponse[RoleRead], status_code=status.HTTP_201_CREATED
)
def create_role(
    db: DbSessionDep,
    _: RoleCreateDep,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
) -> SuccessResponse[RoleRead]:
    payload = RoleCreate(name=name, description=description)
    role = RoleService(db).create(payload)
    return SuccessResponse(message=RoleMessages.CREATED, data=RoleRead.model_validate(role))


@router.get("", response_model=SuccessResponse[Page[RoleRead]])
def list_roles(
    db: DbSessionDep, _: RoleViewDep, params: PaginationDep
) -> SuccessResponse[Page[RoleRead]]:
    items, total = RoleService(db).list(params)
    page = Page[RoleRead].create(
        items=[RoleRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=RoleMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{role_id}", response_model=SuccessResponse[RoleRead])
def edit_role(role_id: UUID, db: DbSessionDep, _: RoleViewDep) -> SuccessResponse[RoleRead]:
    role = RoleService(db).get(role_id)
    return SuccessResponse(message=RoleMessages.RETRIEVED, data=RoleRead.model_validate(role))


@router.patch("/update/{role_id}", response_model=SuccessResponse[RoleRead])
def update_role(
    role_id: UUID,
    db: DbSessionDep,
    _: RoleUpdateDep,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
) -> SuccessResponse[RoleRead]:
    payload = RoleUpdate(name=name, description=description)
    role = RoleService(db).update(role_id, payload)
    return SuccessResponse(message=RoleMessages.UPDATED, data=RoleRead.model_validate(role))


@router.put("/update/{role_id}/permissions", response_model=SuccessResponse[RoleRead])
def set_role_permissions(
    role_id: UUID,
    db: DbSessionDep,
    _: RoleUpdateDep,
    permission_ids: Annotated[list[UUID], Form(default_factory=list)],
) -> SuccessResponse[RoleRead]:
    role = RoleService(db).set_permissions(role_id, permission_ids)
    return SuccessResponse(
        message=RoleMessages.PERMISSIONS_UPDATED, data=RoleRead.model_validate(role)
    )


@router.delete("/delete/{role_id}", response_model=SuccessResponse[None])
def delete_role(role_id: UUID, db: DbSessionDep, _: RoleDeleteDep) -> SuccessResponse[None]:
    RoleService(db).delete(role_id)
    return SuccessResponse(message=RoleMessages.DELETED, data=None)
