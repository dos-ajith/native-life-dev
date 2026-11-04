from fastapi import APIRouter, status

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    GoogleTokenVerifierDep,
    SettingsDep,
)
from app.api.v1.auth.responses import authenticated_result, registration_token_ttl_seconds
from app.core.messages import AuthMessages
from app.core.openapi_tags import ApiTag
from app.schemas.auth import AuthenticatedResult, CompleteRegistrationRequest
from app.schemas.google_auth import (
    GoogleIdTokenRequest,
    GoogleRegistrationRequiredResult,
    GoogleSignInResult,
    LinkedIdentityRead,
)
from app.schemas.response import SuccessResponse
from app.services.google_auth_service import GoogleAuthService
from app.services.registration_details import RegistrationDetails

router = APIRouter(prefix="/auth/google", tags=[ApiTag.AUTH_GOOGLE])


@router.post("/sign-in", response_model=SuccessResponse[GoogleSignInResult])
def sign_in(
    payload: GoogleIdTokenRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    verifier: GoogleTokenVerifierDep,
) -> SuccessResponse[AuthenticatedResult | GoogleRegistrationRequiredResult]:
    outcome = GoogleAuthService(db, settings, verifier).sign_in(payload.id_token)
    if outcome.session is not None and outcome.user is not None:
        return SuccessResponse(
            message=AuthMessages.LOGIN_SUCCESSFUL,
            data=authenticated_result(outcome.session, outcome.user, db),
        )
    assert outcome.registration_token is not None and outcome.identity is not None
    assert outcome.identity.email is not None
    return SuccessResponse(
        message=AuthMessages.REGISTRATION_REQUIRED,
        data=GoogleRegistrationRequiredResult(
            registration_token=outcome.registration_token,
            registration_token_expires_in_seconds=registration_token_ttl_seconds(
                settings.registration_token_expire_minutes
            ),
            email=outcome.identity.email,
            first_name=outcome.identity.given_name,
            last_name=outcome.identity.family_name,
        ),
    )


@router.post(
    "/register",
    response_model=SuccessResponse[AuthenticatedResult],
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: CompleteRegistrationRequest,
    db: DbSessionDep,
    settings: SettingsDep,
    verifier: GoogleTokenVerifierDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[AuthenticatedResult]:
    session, user = GoogleAuthService(db, settings, verifier).register(
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


@router.post("/link", response_model=SuccessResponse[LinkedIdentityRead])
def link(
    payload: GoogleIdTokenRequest,
    user: CurrentActiveUserDep,
    db: DbSessionDep,
    settings: SettingsDep,
    verifier: GoogleTokenVerifierDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[LinkedIdentityRead]:
    identity = GoogleAuthService(db, settings, verifier).link(
        user, payload.id_token, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=AuthMessages.GOOGLE_LINKED, data=LinkedIdentityRead.model_validate(identity)
    )
