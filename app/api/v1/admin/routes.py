from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import (
    ActivityRequestMetaDep,
    DbSessionDep,
    PaginationDep,
    ProfileImageDep,
    SettingsDep,
    require_permission,
)
from app.core.messages import UserMessages
from app.core.permissions import PermissionName
from app.models.user import User, UserStatus, UserType
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/admin/users", tags=["admin"])

UserCreateDep = Annotated[User, Depends(require_permission(PermissionName.USER_CREATE))]
UserViewDep = Annotated[User, Depends(require_permission(PermissionName.USER_VIEW))]
UserUpdateDep = Annotated[User, Depends(require_permission(PermissionName.USER_UPDATE))]
UserDeleteDep = Annotated[User, Depends(require_permission(PermissionName.USER_DELETE))]


@router.post(
    "/create", response_model=SuccessResponse[UserRead], status_code=status.HTTP_201_CREATED
)
def create_user(
    db: DbSessionDep,
    admin: UserCreateDep,
    settings: SettingsDep,
    meta: ActivityRequestMetaDep,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    role_ids: Annotated[list[UUID], Form(default_factory=list)],
    phone: Annotated[str | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[UserRead]:
    payload = UserCreate(
        first_name=first_name, last_name=last_name, email=email, phone=phone, password=password
    )
    user = UserService(db).create(
        payload,
        admin,
        meta.ip_address,
        meta.user_agent,
        image=image,
        upload_dir=settings.upload_dir,
        role_ids=role_ids,
    )
    return SuccessResponse(message=UserMessages.CREATED, data=UserRead.model_validate(user))


@router.get("", response_model=SuccessResponse[Page[UserRead]])
def list_users(
    db: DbSessionDep, _: UserViewDep, params: PaginationDep
) -> SuccessResponse[Page[UserRead]]:
    items, total = UserService(db).list(params)
    page = Page[UserRead].create(
        items=[UserRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=UserMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{user_id}", response_model=SuccessResponse[UserRead])
def edit_user(
    user_id: UUID, db: DbSessionDep, _: UserViewDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).get(user_id)
    return SuccessResponse(message=UserMessages.RETRIEVED, data=UserRead.model_validate(user))


@router.patch("/update/{user_id}", response_model=SuccessResponse[UserRead])
def update_user(
    user_id: UUID,
    db: DbSessionDep,
    admin: UserUpdateDep,
    settings: SettingsDep,
    first_name: Annotated[str | None, Form()] = None,
    last_name: Annotated[str | None, Form()] = None,
    email: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    user_status: Annotated[UserStatus | None, Form(alias="status")] = None,
    user_type: Annotated[UserType | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[UserRead]:
    payload = UserUpdate(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        status=user_status,
        user_type=user_type,
    )
    user = UserService(db).update(user_id, payload, admin)
    if image is not None:
        user = UserService(db).update_image_for(user_id, image, settings.upload_dir)
    return SuccessResponse(message=UserMessages.UPDATED, data=UserRead.model_validate(user))


@router.post("/update/{user_id}/image", response_model=SuccessResponse[UserRead])
def update_user_image(
    user_id: UUID,
    db: DbSessionDep,
    _: UserUpdateDep,
    settings: SettingsDep,
    image: ProfileImageDep,
) -> SuccessResponse[UserRead]:
    user = UserService(db).update_image_for(user_id, image, settings.upload_dir)
    return SuccessResponse(
        message=UserMessages.PROFILE_IMAGE_UPDATED, data=UserRead.model_validate(user)
    )


@router.put("/update/{user_id}/roles", response_model=SuccessResponse[UserRead])
def set_user_roles(
    user_id: UUID,
    db: DbSessionDep,
    admin: UserUpdateDep,
    role_ids: Annotated[list[UUID], Form(default_factory=list)],
) -> SuccessResponse[UserRead]:
    user = UserService(db).assign_roles(user_id, role_ids, admin)
    return SuccessResponse(message=UserMessages.ROLES_UPDATED, data=UserRead.model_validate(user))


@router.delete("/delete/{user_id}", response_model=SuccessResponse[None])
def delete_user(
    user_id: UUID, db: DbSessionDep, admin: UserDeleteDep
) -> SuccessResponse[None]:
    UserService(db).delete(user_id, admin)
    return SuccessResponse(message=UserMessages.DELETED, data=None)
