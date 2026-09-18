from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, status

from app.api.deps import CurrentAdminUserDep, DbSessionDep, PaginationDep
from app.core.messages import RoleMessages
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services.role_service import RoleService

router = APIRouter(prefix="/admin/roles", tags=["roles"])


@router.post(
    "/create", response_model=SuccessResponse[RoleRead], status_code=status.HTTP_201_CREATED
)
def create_role(
    db: DbSessionDep,
    _: CurrentAdminUserDep,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
) -> SuccessResponse[RoleRead]:
    payload = RoleCreate(name=name, description=description)
    role = RoleService(db).create(payload)
    return SuccessResponse(message=RoleMessages.CREATED, data=RoleRead.model_validate(role))


@router.get("", response_model=SuccessResponse[Page[RoleRead]])
def list_roles(
    db: DbSessionDep, _: CurrentAdminUserDep, params: PaginationDep
) -> SuccessResponse[Page[RoleRead]]:
    items, total = RoleService(db).list(params)
    page = Page[RoleRead].create(
        items=[RoleRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=RoleMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{role_id}", response_model=SuccessResponse[RoleRead])
def edit_role(role_id: UUID, db: DbSessionDep, _: CurrentAdminUserDep) -> SuccessResponse[RoleRead]:
    role = RoleService(db).get(role_id)
    return SuccessResponse(message=RoleMessages.RETRIEVED, data=RoleRead.model_validate(role))


@router.patch("/update/{role_id}", response_model=SuccessResponse[RoleRead])
def update_role(
    role_id: UUID,
    db: DbSessionDep,
    _: CurrentAdminUserDep,
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
    _: CurrentAdminUserDep,
    permission_ids: Annotated[list[UUID], Form(default_factory=list)],
) -> SuccessResponse[RoleRead]:
    role = RoleService(db).set_permissions(role_id, permission_ids)
    return SuccessResponse(
        message=RoleMessages.PERMISSIONS_UPDATED, data=RoleRead.model_validate(role)
    )


@router.delete("/delete/{role_id}", response_model=SuccessResponse[None])
def delete_role(role_id: UUID, db: DbSessionDep, _: CurrentAdminUserDep) -> SuccessResponse[None]:
    RoleService(db).delete(role_id)
    return SuccessResponse(message=RoleMessages.DELETED, data=None)
