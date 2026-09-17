from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentAdminUserDep, DbSessionDep, PaginationDep
from app.schemas.pagination import Page
from app.schemas.permission import PermissionCreate, PermissionRead, PermissionUpdate
from app.schemas.response import SuccessResponse
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/admin/permissions", tags=["permissions"])


@router.post(
    "/create", response_model=SuccessResponse[PermissionRead], status_code=status.HTTP_201_CREATED
)
def create_permission(
    payload: PermissionCreate, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[PermissionRead]:
    permission = PermissionService(db).create(payload)
    return SuccessResponse(
        message="Permission created", data=PermissionRead.model_validate(permission)
    )


@router.get("", response_model=SuccessResponse[Page[PermissionRead]])
def list_permissions(
    db: DbSessionDep, _: CurrentAdminUserDep, params: PaginationDep
) -> SuccessResponse[Page[PermissionRead]]:
    items, total = PermissionService(db).list(params)
    page = Page[PermissionRead].create(
        items=[PermissionRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message="Permissions retrieved", data=page)


@router.get("/edit/{permission_id}", response_model=SuccessResponse[PermissionRead])
def edit_permission(
    permission_id: UUID, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[PermissionRead]:
    permission = PermissionService(db).get(permission_id)
    return SuccessResponse(
        message="Permission retrieved", data=PermissionRead.model_validate(permission)
    )


@router.patch("/update/{permission_id}", response_model=SuccessResponse[PermissionRead])
def update_permission(
    permission_id: UUID, payload: PermissionUpdate, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[PermissionRead]:
    permission = PermissionService(db).update(permission_id, payload)
    return SuccessResponse(
        message="Permission updated", data=PermissionRead.model_validate(permission)
    )


@router.delete("/delete/{permission_id}", response_model=SuccessResponse[None])
def delete_permission(
    permission_id: UUID, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[None]:
    PermissionService(db).delete(permission_id)
    return SuccessResponse(message="Permission deleted", data=None)
