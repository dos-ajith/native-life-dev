from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.active_token import ActiveToken


class ActiveTokenRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def activate(self, jti: UUID, expires_at: datetime) -> None:
        self._db.execute(delete(ActiveToken).where(ActiveToken.expires_at < datetime.now(UTC)))
        self._db.add(ActiveToken(jti=jti, expires_at=expires_at))

    def deactivate(self, jti: UUID) -> None:
        self._db.execute(delete(ActiveToken).where(ActiveToken.jti == jti))

    def is_active(self, jti: UUID) -> bool:
        return (
            self._db.scalar(
                select(ActiveToken.jti).where(
                    ActiveToken.jti == jti, ActiveToken.expires_at > datetime.now(UTC)
                )
            )
            is not None
        )
