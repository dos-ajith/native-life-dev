from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.timezone import app_now
from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, token: RefreshToken) -> None:
        self._db.add(token)

    def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        return self._db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )

    def revoke_for_access_token(self, access_token_jti: UUID) -> None:
        self._db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.access_token_jti == access_token_jti,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=app_now())
        )
