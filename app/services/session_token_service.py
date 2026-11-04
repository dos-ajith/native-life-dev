from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.jwt import create_access_token
from app.core.messages import AuthMessages
from app.core.security import generate_refresh_token, hash_token
from app.core.timezone import app_now
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserStatus
from app.repositories.active_token_repository import ActiveTokenRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime


class SessionTokenService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._active_tokens = ActiveTokenRepository(db)
        self._refresh_tokens = RefreshTokenRepository(db)
        self._users = UserRepository(db)

    def issue(self, user: User) -> IssuedSession:
        access = create_access_token(user.id, self._settings)
        self._active_tokens.activate(access.jti, access.expires_at)
        raw_refresh_token = generate_refresh_token()
        self._refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw_refresh_token),
                access_token_jti=access.jti,
                expires_at=app_now() + timedelta(days=self._settings.refresh_token_expire_days),
            )
        )
        self._db.commit()
        return IssuedSession(
            access_token=access.token,
            refresh_token=raw_refresh_token,
            access_token_expires_at=access.expires_at,
        )

    def rotate(self, raw_refresh_token: str) -> tuple[IssuedSession, User]:
        record = self._refresh_tokens.get_by_hash_for_update(hash_token(raw_refresh_token))
        if record is None or record.revoked_at is not None or record.expires_at <= app_now():
            raise AuthenticationError(AuthMessages.INVALID_REFRESH_TOKEN)
        self._revoke(record)
        user = self._users.get_by_id(record.user_id)
        if user is None:
            self._db.commit()
            raise AuthenticationError(AuthMessages.INVALID_REFRESH_TOKEN)
        if user.status != UserStatus.ACTIVE:
            self._db.commit()
            raise AuthorizationError(AuthMessages.ACCOUNT_INACTIVE)
        return self.issue(user), user

    def revoke_for_access_token(self, access_token_jti: UUID) -> None:
        self._refresh_tokens.revoke_for_access_token(access_token_jti)

    def _revoke(self, record: RefreshToken) -> None:
        record.revoked_at = app_now()
        self._active_tokens.deactivate(record.access_token_jti)
