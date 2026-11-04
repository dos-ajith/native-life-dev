from fastapi import APIRouter, BackgroundTasks

from app.api.deps import (
    CurrentActiveUserDep,
    CurrentUserDep,
    DbSessionDep,
    SettingsDep,
    TokenClaimsDep,
)
from app.api.v1.auth.responses import authenticated_user, token_response
from app.core.messages import AuthMessages
from app.core.openapi_tags import ApiTag
from app.schemas.auth import (
    AuthenticatedUserRead,
    EmailVerificationResult,
    LinkEmailRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResendEmailVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.response import SuccessResponse
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService

router = APIRouter(prefix="/auth", tags=[ApiTag.AUTH_EMAIL])


@router.post("/login", response_model=SuccessResponse[TokenResponse])
def login(
    payload: LoginRequest, db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[TokenResponse]:
    session, user = AuthService(db, settings).authenticate(payload.email, payload.password)
    return SuccessResponse(
        message=AuthMessages.LOGIN_SUCCESSFUL, data=token_response(session, user, db)
    )


@router.post("/refresh", response_model=SuccessResponse[TokenResponse])
def refresh(
    payload: RefreshTokenRequest, db: DbSessionDep, settings: SettingsDep
) -> SuccessResponse[TokenResponse]:
    session, user = AuthService(db, settings).refresh(payload.refresh_token)
    return SuccessResponse(
        message=AuthMessages.TOKEN_REFRESHED, data=token_response(session, user, db)
    )


@router.get("/me", response_model=SuccessResponse[AuthenticatedUserRead])
def me(user: CurrentUserDep, db: DbSessionDep) -> SuccessResponse[AuthenticatedUserRead]:
    return SuccessResponse(
        message=AuthMessages.PROFILE_RETRIEVED, data=authenticated_user(user, db)
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
        data=EmailVerificationResult(email=payload.email, email_verified_at=user.email_verified_at),
    )


@router.post("/resend-email-verification", response_model=SuccessResponse[None])
def resend_email_verification(
    payload: ResendEmailVerificationRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
) -> SuccessResponse[None]:
    EmailVerificationService(db, settings).resend(payload.email, background_tasks)
    return SuccessResponse(message=AuthMessages.VERIFICATION_CODE_SENT, data=None)


@router.post("/email/link/request-otp", response_model=SuccessResponse[None])
def request_link_email_otp(
    payload: LinkEmailRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[None]:
    EmailVerificationService(db, settings).send_link_otp(
        current_user, payload.email, background_tasks
    )
    return SuccessResponse(message=AuthMessages.VERIFICATION_CODE_SENT, data=None)


@router.post("/email/link/verify-otp", response_model=SuccessResponse[AuthenticatedUserRead])
def verify_link_email_otp(
    payload: VerifyEmailRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[AuthenticatedUserRead]:
    user = EmailVerificationService(db, settings).link_email(
        current_user, payload.email, payload.otp
    )
    return SuccessResponse(message=AuthMessages.EMAIL_VERIFIED, data=authenticated_user(user, db))
