from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import (
    CurrentAdminUserDep,
    DbSessionDep,
    PaginationDep,
    ProfileImageDep,
    SettingsDep,
)
from app.core.messages import UserMessages
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.user import UserCreate, UserRead, UserRolesAssign, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.post(
    "/create", response_model=SuccessResponse[UserRead], status_code=status.HTTP_201_CREATED
)
def create_user(
    payload: UserCreate, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).create(payload)
    return SuccessResponse(message=UserMessages.CREATED, data=UserRead.model_validate(user))


@router.get("", response_model=SuccessResponse[Page[UserRead]])
def list_users(
    db: DbSessionDep, _: CurrentAdminUserDep, params: PaginationDep
) -> SuccessResponse[Page[UserRead]]:
    items, total = UserService(db).list(params)
    page = Page[UserRead].create(
        items=[UserRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=UserMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{user_id}", response_model=SuccessResponse[UserRead])
def edit_user(
    user_id: UUID, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).get(user_id)
    return SuccessResponse(message=UserMessages.RETRIEVED, data=UserRead.model_validate(user))


@router.patch("/update/{user_id}", response_model=SuccessResponse[UserRead])
def update_user(
    user_id: UUID, payload: UserUpdate, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).update(user_id, payload)
    return SuccessResponse(message=UserMessages.UPDATED, data=UserRead.model_validate(user))


@router.post("/update/{user_id}/image", response_model=SuccessResponse[UserRead])
def update_user_image(
    user_id: UUID,
    db: DbSessionDep,
    _: CurrentAdminUserDep,
    settings: SettingsDep,
    image: ProfileImageDep,
) -> SuccessResponse[UserRead]:
    user = UserService(db).update_image_for(user_id, image, settings.upload_dir)
    return SuccessResponse(
        message=UserMessages.PROFILE_IMAGE_UPDATED, data=UserRead.model_validate(user)
    )


@router.put("/update/{user_id}/roles", response_model=SuccessResponse[UserRead])
def set_user_roles(
    user_id: UUID, payload: UserRolesAssign, db: DbSessionDep, _: CurrentAdminUserDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).assign_roles(user_id, payload.role_ids)
    return SuccessResponse(
        message=UserMessages.ROLES_UPDATED, data=UserRead.model_validate(user)
    )


@router.delete("/delete/{user_id}", response_model=SuccessResponse[None])
def delete_user(
    user_id: UUID, db: DbSessionDep, admin: CurrentAdminUserDep
) -> SuccessResponse[None]:
    UserService(db).delete(user_id, admin)
    return SuccessResponse(message=UserMessages.DELETED, data=None)
