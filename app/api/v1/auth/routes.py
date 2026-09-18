from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSessionDep, SettingsDep, TokenClaimsDep
from app.core.messages import AuthMessages
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.response import SuccessResponse
from app.schemas.user import AuthenticatedUserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SuccessResponse[TokenResponse])
def login(
    payload: LoginRequest, db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[TokenResponse]:
    token, user = AuthService(db, settings).authenticate(payload.email, payload.password)
    return SuccessResponse(
        message=AuthMessages.LOGIN_SUCCESSFUL,
        data=TokenResponse(access_token=token, user=AuthenticatedUserRead.model_validate(user)),
    )


@router.get("/me", response_model=SuccessResponse[AuthenticatedUserRead])
def me(user: CurrentUserDep) -> SuccessResponse[AuthenticatedUserRead]:
    return SuccessResponse(
        message=AuthMessages.PROFILE_RETRIEVED, data=AuthenticatedUserRead.model_validate(user)
    )


@router.post("/logout", response_model=SuccessResponse[None])
def logout(
    claims: TokenClaimsDep,
    user: CurrentUserDep,
    db: DbSessionDep,
    settings: SettingsDep,
) -> SuccessResponse[None]:
    AuthService(db, settings).logout(claims.jti)
    return SuccessResponse(message=AuthMessages.LOGGED_OUT, data=None)
