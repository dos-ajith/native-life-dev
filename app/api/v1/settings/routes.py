from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, status

from app.api.deps import DbSessionDep, PaginationDep, require_permission
from app.core.messages import SettingMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.setting import SettingCreate, SettingRead, SettingUpdate
from app.services.setting_service import SettingService

router = APIRouter(prefix="/admin/settings", tags=["settings"])

SettingCreateDep = Annotated[User, Depends(require_permission(PermissionName.SETTING_CREATE))]
SettingViewDep = Annotated[User, Depends(require_permission(PermissionName.SETTING_VIEW))]
SettingUpdateDep = Annotated[User, Depends(require_permission(PermissionName.SETTING_UPDATE))]
SettingDeleteDep = Annotated[User, Depends(require_permission(PermissionName.SETTING_DELETE))]


@router.post(
    "/create", response_model=SuccessResponse[SettingRead], status_code=status.HTTP_201_CREATED
)
def create_setting(
    db: DbSessionDep,
    _: SettingCreateDep,
    key: Annotated[str, Form()],
    value: Annotated[str | None, Form()] = None,
) -> SuccessResponse[SettingRead]:
    payload = SettingCreate(key=key, value=value)
    setting = SettingService(db).create(payload)
    return SuccessResponse(
        message=SettingMessages.CREATED, data=SettingRead.model_validate(setting)
    )


@router.get("", response_model=SuccessResponse[Page[SettingRead]])
def list_settings(
    db: DbSessionDep, _: SettingViewDep, params: PaginationDep
) -> SuccessResponse[Page[SettingRead]]:
    items, total = SettingService(db).list(params)
    page = Page[SettingRead].create(
        items=[SettingRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=SettingMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{setting_id}", response_model=SuccessResponse[SettingRead])
def edit_setting(
    setting_id: UUID, db: DbSessionDep, _: SettingViewDep
) -> SuccessResponse[SettingRead]:
    setting = SettingService(db).get(setting_id)
    return SuccessResponse(
        message=SettingMessages.RETRIEVED, data=SettingRead.model_validate(setting)
    )


@router.get("/key/{key}", response_model=SuccessResponse[SettingRead])
def get_setting_by_key(
    key: str, db: DbSessionDep, _: SettingViewDep
) -> SuccessResponse[SettingRead]:
    setting = SettingService(db).get_by_key(key)
    return SuccessResponse(
        message=SettingMessages.RETRIEVED, data=SettingRead.model_validate(setting)
    )


@router.patch("/update/{setting_id}", response_model=SuccessResponse[SettingRead])
def update_setting(
    setting_id: UUID,
    db: DbSessionDep,
    _: SettingUpdateDep,
    key: Annotated[str | None, Form()] = None,
    value: Annotated[str | None, Form()] = None,
) -> SuccessResponse[SettingRead]:
    payload = SettingUpdate(key=key, value=value)
    setting = SettingService(db).update(setting_id, payload)
    return SuccessResponse(
        message=SettingMessages.UPDATED, data=SettingRead.model_validate(setting)
    )


@router.delete("/delete/{setting_id}", response_model=SuccessResponse[None])
def delete_setting(
    setting_id: UUID, db: DbSessionDep, _: SettingDeleteDep
) -> SuccessResponse[None]:
    SettingService(db).delete(setting_id)
    return SuccessResponse(message=SettingMessages.DELETED, data=None)
