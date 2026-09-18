from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, ProfileImageDep, SettingsDep
from app.core.messages import UserMessages
from app.schemas.response import SuccessResponse
from app.schemas.user import UserCreate, UserRead, UserSelfUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/register", response_model=SuccessResponse[UserRead], status_code=status.HTTP_201_CREATED
)
def register_user(payload: UserCreate, db: DbSessionDep) -> SuccessResponse[UserRead]:
    user = UserService(db).register(payload)
    return SuccessResponse(message=UserMessages.REGISTERED, data=UserRead.model_validate(user))


@router.patch("/me", response_model=SuccessResponse[UserRead])
def update_me(
    payload: UserSelfUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).update_self(current_user, payload)
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
