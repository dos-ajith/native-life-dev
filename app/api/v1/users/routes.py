from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    ProfileImageDep,
    SettingsDep,
)
from app.core.messages import UserMessages
from app.schemas.response import SuccessResponse
from app.schemas.user import UserCreate, UserRead, UserSelfUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/register", response_model=SuccessResponse[UserRead], status_code=status.HTTP_201_CREATED
)
def register_user(
    db: DbSessionDep,
    settings: SettingsDep,
    meta: ActivityRequestMetaDep,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[UserRead]:
    payload = UserCreate(
        first_name=first_name, last_name=last_name, email=email, phone=phone, password=password
    )
    user = UserService(db).register(
        payload, meta.ip_address, meta.user_agent, image=image, upload_dir=settings.upload_dir
    )
    return SuccessResponse(message=UserMessages.REGISTERED, data=UserRead.model_validate(user))


@router.patch("/me", response_model=SuccessResponse[UserRead])
def update_me(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    first_name: Annotated[str | None, Form()] = None,
    last_name: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[UserRead]:
    payload = UserSelfUpdate(first_name=first_name, last_name=last_name, phone=phone)
    user = UserService(db).update_self(current_user, payload)
    if image is not None:
        user = UserService(db).update_image(user, image, settings.upload_dir)
    return SuccessResponse(
        message=UserMessages.PROFILE_UPDATED, data=UserRead.model_validate(user)
    )


@router.post("/me/image", response_model=SuccessResponse[UserRead])
def update_me_image(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    image: ProfileImageDep,
) -> SuccessResponse[UserRead]:
    user = UserService(db).update_image(current_user, image, settings.upload_dir)
    return SuccessResponse(
        message=UserMessages.PROFILE_IMAGE_UPDATED, data=UserRead.model_validate(user)
    )
