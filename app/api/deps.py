from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, File, Query, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.google_auth import GoogleTokenVerifier, get_google_token_verifier
from app.core.jwt import TokenClaims, parse_token_claims
from app.core.messages import AuthMessages
from app.core.sms import SmsProvider, get_sms_provider
from app.models.user import User
from app.schemas.geography import ReverseGeocodeQuery
from app.schemas.pagination import PaginationParams
from app.services.authorization_service import (
    guest_has_permission,
    has_any_permission,
    has_permission,
    is_super_admin,
)
from app.services.token_authentication_service import TokenAuthenticationService, ensure_active_user

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[Session, Depends(get_db)]


def get_sms_provider_dependency(settings: SettingsDep) -> SmsProvider | None:
    return get_sms_provider(settings)


SmsProviderDep = Annotated[SmsProvider | None, Depends(get_sms_provider_dependency)]


def get_google_token_verifier_dependency(settings: SettingsDep) -> GoogleTokenVerifier | None:
    return get_google_token_verifier(settings)


GoogleTokenVerifierDep = Annotated[
    GoogleTokenVerifier | None, Depends(get_google_token_verifier_dependency)
]

_bearer_scheme = HTTPBearer(auto_error=False)


def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: SettingsDep,
) -> TokenClaims:
    if credentials is None:
        raise AuthenticationError(AuthMessages.MISSING_TOKEN)
    return parse_token_claims(credentials.credentials, settings)


TokenClaimsDep = Annotated[TokenClaims, Depends(get_token_claims)]


def get_optional_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: SettingsDep,
) -> TokenClaims | None:
    if credentials is None:
        return None
    return get_token_claims(credentials, settings)


OptionalTokenClaimsDep = Annotated[TokenClaims | None, Depends(get_optional_token_claims)]


def get_current_user(claims: TokenClaimsDep, db: DbSessionDep) -> User:
    return TokenAuthenticationService(db).get_user_for_claims(claims)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_active_user(user: CurrentUserDep) -> User:
    ensure_active_user(user)
    return user


CurrentActiveUserDep = Annotated[User, Depends(get_current_active_user)]


def require_permission(permission: str) -> Callable[[User], User]:
    def dependency(user: CurrentActiveUserDep) -> User:
        if not has_permission(user, permission):
            raise AuthorizationError(AuthMessages.PERMISSION_DENIED)
        return user

    return dependency


def require_super_admin(user: CurrentActiveUserDep) -> User:
    if not is_super_admin(user):
        raise AuthorizationError(AuthMessages.PERMISSION_DENIED)
    return user


SuperAdminDep = Annotated[User, Depends(require_super_admin)]


def require_any_permission(*permissions: str) -> Callable[[User], User]:
    def dependency(user: CurrentActiveUserDep) -> User:
        if not has_any_permission(user, permissions):
            raise AuthorizationError(AuthMessages.PERMISSION_DENIED)
        return user

    return dependency


def get_optional_active_user(claims: OptionalTokenClaimsDep, db: DbSessionDep) -> User | None:
    if claims is None:
        return None
    return get_current_active_user(get_current_user(claims, db))


OptionalActiveUserDep = Annotated[User | None, Depends(get_optional_active_user)]


def require_permission_or_guest(
    permission: str,
) -> Callable[[User | None], User | None]:
    def dependency(user: OptionalActiveUserDep) -> User | None:
        if user is not None and has_permission(user, permission):
            return user
        if guest_has_permission(permission):
            return user
        if user is None:
            raise AuthenticationError(AuthMessages.MISSING_TOKEN)
        raise AuthorizationError(AuthMessages.PERMISSION_DENIED)

    return dependency


def get_pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]

ProfileImageDep = Annotated[UploadFile, File(...)]


def get_reverse_geocode_params(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
) -> ReverseGeocodeQuery:
    return ReverseGeocodeQuery(latitude=latitude, longitude=longitude)


ReverseGeocodeQueryDep = Annotated[ReverseGeocodeQuery, Depends(get_reverse_geocode_params)]


@dataclass
class ActivityRequestMeta:
    ip_address: str | None
    user_agent: str | None


def get_activity_request_meta(request: Request) -> ActivityRequestMeta:
    return ActivityRequestMeta(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


ActivityRequestMetaDep = Annotated[ActivityRequestMeta, Depends(get_activity_request_meta)]
