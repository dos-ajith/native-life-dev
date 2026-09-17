from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSessionDep, SettingsDep, TokenClaimsDep
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.response import SuccessResponse
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SuccessResponse[TokenResponse])
def login(
    payload: LoginRequest, db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[TokenResponse]:
    token = AuthService(db, settings).authenticate(payload.email, payload.password)
    return SuccessResponse(message="Login successful", data=TokenResponse(access_token=token))


@router.get("/me", response_model=SuccessResponse[UserRead])
def me(user: CurrentUserDep) -> SuccessResponse[UserRead]:
    return SuccessResponse(message="User profile retrieved", data=UserRead.model_validate(user))


@router.post("/logout", response_model=SuccessResponse[None])
def logout(
    claims: TokenClaimsDep,
    user: CurrentUserDep,
    db: DbSessionDep,
    settings: SettingsDep,
) -> SuccessResponse[None]:
    AuthService(db, settings).logout(claims.jti)
    return SuccessResponse(message="Logged out", data=None)
