from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.jwt import parse_token_claims
from app.services.token_authentication_service import (
    TokenAuthenticationService,
    ensure_active_user,
)


@dataclass(frozen=True)
class AuthenticatedSocketIdentity:
    user_id: UUID
    token_id: UUID
    expires_at: datetime


class WebSocketAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self, raw_token: str) -> AuthenticatedSocketIdentity:
        return await run_in_threadpool(self._authenticate_blocking, raw_token)

    def _authenticate_blocking(self, raw_token: str) -> AuthenticatedSocketIdentity:
        claims = parse_token_claims(raw_token, self._settings)
        with SessionLocal() as db:
            user = TokenAuthenticationService(db).get_user_for_claims(claims)
            ensure_active_user(user)
            return AuthenticatedSocketIdentity(
                user_id=user.id, token_id=claims.jti, expires_at=claims.expires_at
            )
