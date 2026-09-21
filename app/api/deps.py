from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, File, Query, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.formatting_context import (
    APP_DATE_FORMAT_SETTING_KEY,
    APP_TIME_FORMAT_SETTING_KEY,
    DEFAULT_APP_DATE_FORMAT,
    DEFAULT_APP_TIME_FORMAT,
    set_datetime_formats,
)
from app.core.jwt import decode_access_token
from app.core.messages import AuthMessages
from app.models.user import User, UserStatus, UserType
from app.repositories.active_token_repository import ActiveTokenRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.user_repository import UserRepository
from app.schemas.geography import ReverseGeocodeQuery
from app.schemas.pagination import PaginationParams

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[Session, Depends(get_db)]

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class TokenClaims:
    user_id: UUID
    jti: UUID
    expires_at: datetime


def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: SettingsDep,
) -> TokenClaims:
    if credentials is None:
        raise AuthenticationError(AuthMessages.MISSING_TOKEN)
    try:
        payload = decode_access_token(credentials.credentials, settings)
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            jti=UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AuthenticationError(AuthMessages.INVALID_TOKEN) from exc


TokenClaimsDep = Annotated[TokenClaims, Depends(get_token_claims)]


def get_current_user(claims: TokenClaimsDep, db: DbSessionDep) -> User:
    if not ActiveTokenRepository(db).is_active(claims.jti):
        raise AuthenticationError(AuthMessages.INVALID_TOKEN)
    user = UserRepository(db).get_by_id(claims.user_id)
    if user is None:
        raise AuthenticationError(AuthMessages.INVALID_TOKEN)
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_active_user(user: CurrentUserDep) -> User:
    if user.status != UserStatus.ACTIVE:
        raise AuthorizationError(AuthMessages.ACCOUNT_INACTIVE)
    return user


CurrentActiveUserDep = Annotated[User, Depends(get_current_active_user)]


def get_current_admin_user(user: CurrentActiveUserDep) -> User:
    if user.user_type != UserType.PRIVATE:
        raise AuthorizationError(AuthMessages.ADMIN_REQUIRED)
    return user


CurrentAdminUserDep = Annotated[User, Depends(get_current_admin_user)]


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


def apply_datetime_formats(db: DbSessionDep) -> None:
    settings = SettingRepository(db)
    date_setting = settings.get_by_key(APP_DATE_FORMAT_SETTING_KEY)
    time_setting = settings.get_by_key(APP_TIME_FORMAT_SETTING_KEY)
    set_datetime_formats(
        date_setting.value if date_setting and date_setting.value else DEFAULT_APP_DATE_FORMAT,
        time_setting.value if time_setting and time_setting.value else DEFAULT_APP_TIME_FORMAT,
    )
