from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile, status

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    ProfileImageDep,
    SettingsDep,
)
from app.core.messages import UserMessages
from app.core.openapi_tags import ApiTag
from app.models.user import UserGender
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.schemas.user import (
    UserCreate,
    UserDiscoveryRead,
    UserProfileRead,
    UserRead,
    UserRegistrationResult,
    UserSelfUpdate,
)
from app.services.account_role_status_service import AccountRoleStatusService
from app.services.user_service import UserService

MAX_SEARCH_LENGTH = 100

router = APIRouter(prefix="/users")


@router.post(
    "/register",
    tags=[ApiTag.AUTH_EMAIL],
    response_model=SuccessResponse[UserRegistrationResult],
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    db: DbSessionDep,
    settings: SettingsDep,
    meta: ActivityRequestMetaDep,
    background_tasks: BackgroundTasks,
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
    gender: Annotated[UserGender | None, Form()] = None,
    date_of_birth: Annotated[date | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[UserRegistrationResult]:
    payload = UserCreate(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        password=password,
        gender=gender,
        date_of_birth=date_of_birth,
    )
    user = UserService(db).register(
        payload,
        settings,
        background_tasks,
        meta.ip_address,
        meta.user_agent,
        image=image,
        upload_dir=settings.upload_dir,
    )
    return SuccessResponse(
        message=UserMessages.REGISTERED, data=UserRegistrationResult(email=user.email)
    )


@router.get("", tags=[ApiTag.USER_FOLLOWS], response_model=SuccessResponse[Page[UserDiscoveryRead]])
def list_users(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    search: Annotated[str | None, Query(max_length=MAX_SEARCH_LENGTH)] = None,
) -> SuccessResponse[Page[UserDiscoveryRead]]:
    items, total = UserService(db).list_discoverable(current_user, search, params)
    page = Page[UserDiscoveryRead].create(items=list(items), total=total, params=params)
    return SuccessResponse(message=UserMessages.LIST_RETRIEVED, data=page)


@router.patch("/me", tags=[ApiTag.PROFILE], response_model=SuccessResponse[UserRead])
def update_me(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    first_name: Annotated[str | None, Form()] = None,
    last_name: Annotated[str | None, Form()] = None,
    gender: Annotated[UserGender | None, Form()] = None,
    date_of_birth: Annotated[date | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[UserRead]:
    payload = UserSelfUpdate(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=date_of_birth,
    )
    user = UserService(db).update_self(current_user, payload)
    if image is not None:
        user = UserService(db).update_image(user, image, settings.upload_dir)
    return SuccessResponse(
        message=UserMessages.PROFILE_UPDATED,
        data=UserRead.from_user(user, AccountRoleStatusService(db).describe(user)),
    )


@router.post("/me/image", tags=[ApiTag.PROFILE], response_model=SuccessResponse[UserRead])
def update_me_image(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    image: ProfileImageDep,
) -> SuccessResponse[UserRead]:
    user = UserService(db).update_image(current_user, image, settings.upload_dir)
    return SuccessResponse(
        message=UserMessages.PROFILE_IMAGE_UPDATED,
        data=UserRead.from_user(user, AccountRoleStatusService(db).describe(user)),
    )


@router.get(
    "/{user_id}/profile",
    tags=[ApiTag.USER_FOLLOWS],
    response_model=SuccessResponse[UserProfileRead],
    summary="Get a user's public profile",
    description=(
        "Returns the public profile of another user, including follower, following and "
        "published post counts and the relationship between the caller and that user."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def get_user_profile(
    user_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserProfileRead]:
    profile = UserService(db).get_profile(current_user, user_id)
    return SuccessResponse(message=UserMessages.PROFILE_RETRIEVED, data=profile)
