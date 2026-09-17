from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.jwt import decode_access_token
from app.models.user import User, UserStatus
from app.repositories.active_token_repository import ActiveTokenRepository
from app.repositories.user_repository import UserRepository

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
        raise AuthenticationError("Missing authentication token")
    try:
        payload = decode_access_token(credentials.credentials, settings)
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            jti=UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired token") from exc


TokenClaimsDep = Annotated[TokenClaims, Depends(get_token_claims)]


def get_current_user(claims: TokenClaimsDep, db: DbSessionDep) -> User:
    if not ActiveTokenRepository(db).is_active(claims.jti):
        raise AuthenticationError("Invalid or expired token")
    user = UserRepository(db).get_by_id(claims.user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired token")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_active_user(user: CurrentUserDep) -> User:
    if user.status != UserStatus.ACTIVE:
        raise AuthorizationError("Account is not active")
    return user


CurrentActiveUserDep = Annotated[User, Depends(get_current_active_user)]
