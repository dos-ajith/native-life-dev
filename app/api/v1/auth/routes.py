from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSessionDep, SettingsDep, TokenClaimsDep
from app.core.messages import AuthMessages
from app.schemas.auth import (
    EmailVerificationResult,
    LoginRequest,
    ResendEmailVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.response import SuccessResponse
from app.schemas.user import AuthenticatedUserRead
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService

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


@router.post("/verify-email", response_model=SuccessResponse[EmailVerificationResult])
def verify_email(
    payload: VerifyEmailRequest, db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[EmailVerificationResult]:
    user, already_verified = EmailVerificationService(db, settings).verify(
        payload.email, payload.otp
    )
    message = (
        AuthMessages.EMAIL_ALREADY_VERIFIED if already_verified else AuthMessages.EMAIL_VERIFIED
    )
    return SuccessResponse(
        message=message,
        data=EmailVerificationResult(email=user.email, email_verified_at=user.email_verified_at),
    )


@router.post("/resend-email-verification", response_model=SuccessResponse[None])
def resend_email_verification(
    payload: ResendEmailVerificationRequest, db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[None]:
    EmailVerificationService(db, settings).resend(payload.email)
    return SuccessResponse(message=AuthMessages.VERIFICATION_CODE_SENT, data=None)
