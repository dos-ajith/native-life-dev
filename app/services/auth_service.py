import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.messages import AuthMessages
from app.core.security import verify_password
from app.models.user import User, UserStatus, UserType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.active_token_repository import ActiveTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.session_token_service import IssuedSession, SessionTokenService

logger = logging.getLogger("app.auth")


class AuthService:
    def __init__(
        self, db: Session, settings: Settings, publisher: RealtimePublisher | None = None
    ) -> None:
        self._db = db
        self._publisher = publisher or get_realtime_publisher()
        self._users = UserRepository(db)
        self._active_tokens = ActiveTokenRepository(db)
        self._sessions = SessionTokenService(db, settings)

    def authenticate(self, email: str, password: str) -> tuple[IssuedSession, User]:
        user = self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError(AuthMessages.INVALID_CREDENTIALS)
        if user.user_type == UserType.PUBLIC and user.email_verified_at is None:
            raise AuthenticationError(AuthMessages.EMAIL_NOT_VERIFIED)
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError(AuthMessages.ACCOUNT_INACTIVE)
        return self._sessions.issue(user), user

    def refresh(self, refresh_token: str) -> tuple[IssuedSession, User]:
        return self._sessions.rotate(refresh_token)

    def logout(self, jti: UUID) -> None:
        self._active_tokens.deactivate(jti)
        self._sessions.revoke_for_access_token(jti)
        self._db.commit()
        try:
            self._publisher.disconnect_token(jti)
        except Exception:
            logger.exception("Failed to close WebSocket connections for revoked token")
