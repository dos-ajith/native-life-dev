from fastapi import APIRouter, status

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    SettingsDep,
    SmsProviderDep,
)
from app.api.v1.auth.responses import (
    authenticated_result,
    authenticated_user,
    registration_token_ttl_seconds,
)
from app.core.messages import AuthMessages
from app.core.openapi_tags import ApiTag
from app.schemas.auth import (
    AuthenticatedResult,
    AuthenticatedUserRead,
    CompleteRegistrationRequest,
)
from app.schemas.phone_auth import (
    PhoneOtpRequest,
    PhoneOtpSent,
    PhoneOtpVerifyRequest,
    PhoneRegistrationRequiredResult,
    PhoneVerifyResult,
)
from app.schemas.response import SuccessResponse
from app.services.phone_auth_service import PhoneAuthService
from app.services.registration_details import RegistrationDetails

router = APIRouter(prefix="/auth/phone", tags=[ApiTag.AUTH_PHONE])


@router.post("/request-otp", response_model=SuccessResponse[PhoneOtpSent])
def request_otp(
    payload: PhoneOtpRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sms_provider: SmsProviderDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[PhoneOtpSent]:
    issued = PhoneAuthService(db, settings, sms_provider).send_otp(payload.phone, meta.ip_address)
    return SuccessResponse(
        message=AuthMessages.PHONE_OTP_SENT,
        data=PhoneOtpSent(
            phone=payload.phone,
            expires_in_seconds=issued.expires_in_seconds,
            resend_available_in_seconds=issued.resend_available_in_seconds,
            dev_otp=issued.dev_otp,
        ),
    )


@router.post("/verify-otp", response_model=SuccessResponse[PhoneVerifyResult])
def verify_otp(
    payload: PhoneOtpVerifyRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sms_provider: SmsProviderDep,
) -> SuccessResponse[AuthenticatedResult | PhoneRegistrationRequiredResult]:
    outcome = PhoneAuthService(db, settings, sms_provider).verify_otp(payload.phone, payload.otp)
    if outcome.session is not None and outcome.user is not None:
        return SuccessResponse(
            message=AuthMessages.LOGIN_SUCCESSFUL,
            data=authenticated_result(outcome.session, outcome.user, db),
        )
    assert outcome.registration_token is not None
    return SuccessResponse(
        message=AuthMessages.REGISTRATION_REQUIRED,
        data=PhoneRegistrationRequiredResult(
            phone=payload.phone,
            registration_token=outcome.registration_token,
            registration_token_expires_in_seconds=registration_token_ttl_seconds(
                settings.registration_token_expire_minutes
            ),
        ),
    )


@router.post("/link/request-otp", response_model=SuccessResponse[PhoneOtpSent])
def request_link_otp(
    payload: PhoneOtpRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sms_provider: SmsProviderDep,
    meta: ActivityRequestMetaDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[PhoneOtpSent]:
    issued = PhoneAuthService(db, settings, sms_provider).send_link_otp(
        current_user, payload.phone, meta.ip_address
    )
    return SuccessResponse(
        message=AuthMessages.PHONE_OTP_SENT,
        data=PhoneOtpSent(
            phone=payload.phone,
            expires_in_seconds=issued.expires_in_seconds,
            resend_available_in_seconds=issued.resend_available_in_seconds,
            dev_otp=issued.dev_otp,
        ),
    )


@router.post("/link/verify-otp", response_model=SuccessResponse[AuthenticatedUserRead])
def verify_link_otp(
    payload: PhoneOtpVerifyRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sms_provider: SmsProviderDep,
    meta: ActivityRequestMetaDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[AuthenticatedUserRead]:
    user = PhoneAuthService(db, settings, sms_provider).link_phone(
        current_user, payload.phone, payload.otp, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(message=AuthMessages.PHONE_VERIFIED, data=authenticated_user(user, db))


@router.post(
    "/register",
    response_model=SuccessResponse[AuthenticatedResult],
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: CompleteRegistrationRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    sms_provider: SmsProviderDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[AuthenticatedResult]:
    session, user = PhoneAuthService(db, settings, sms_provider).register(
        RegistrationDetails(
            registration_token=payload.registration_token,
            first_name=payload.first_name,
            last_name=payload.last_name,
            ip_address=meta.ip_address,
            user_agent=meta.user_agent,
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
        )
    )
    return SuccessResponse(
        message=AuthMessages.REGISTRATION_COMPLETED, data=authenticated_result(session, user, db)
    )
