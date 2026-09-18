from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.jwt import create_access_token
from app.core.messages import AuthMessages
from app.core.security import verify_password
from app.models.user import User, UserStatus
from app.repositories.active_token_repository import ActiveTokenRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._users = UserRepository(db)
        self._active_tokens = ActiveTokenRepository(db)
        self._settings = settings

    def authenticate(self, email: str, password: str) -> tuple[str, User]:
        user = self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError(AuthMessages.INVALID_CREDENTIALS)
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError(AuthMessages.ACCOUNT_INACTIVE)
        issued = create_access_token(user.id, self._settings)
        self._active_tokens.activate(issued.jti, issued.expires_at)
        return issued.token, user

    def logout(self, jti: UUID) -> None:
        self._active_tokens.deactivate(jti)
