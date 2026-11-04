from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.jwt import TokenClaims
from app.core.messages import AuthMessages
from app.models.user import User, UserStatus
from app.repositories.active_token_repository import ActiveTokenRepository
from app.repositories.user_repository import UserRepository


def ensure_active_user(user: User) -> None:
    if user.status != UserStatus.ACTIVE:
        raise AuthorizationError(AuthMessages.ACCOUNT_INACTIVE)


class TokenAuthenticationService:
    def __init__(self, db: Session) -> None:
        self._active_tokens = ActiveTokenRepository(db)
        self._users = UserRepository(db)

    def get_user_for_claims(self, claims: TokenClaims) -> User:
        if not self._active_tokens.is_active(claims.jti):
            raise AuthenticationError(AuthMessages.INVALID_TOKEN)
        user = self._users.get_by_id(claims.user_id)
        if user is None:
            raise AuthenticationError(AuthMessages.INVALID_TOKEN)
        return user
