from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.schemas.response import SuccessResponse
from app.schemas.user import UserCreate, UserRead, UserSelfUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/register", response_model=SuccessResponse[UserRead], status_code=status.HTTP_201_CREATED
)
def register_user(payload: UserCreate, db: DbSessionDep) -> SuccessResponse[UserRead]:
    user = UserService(db).register(payload)
    return SuccessResponse(message="Registration successful", data=UserRead.model_validate(user))


@router.patch("/me", response_model=SuccessResponse[UserRead])
def update_me(
    payload: UserSelfUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserRead]:
    user = UserService(db).update_self(current_user, payload)
    return SuccessResponse(message="Profile updated", data=UserRead.model_validate(user))
