from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_identity import AuthIdentity, AuthProvider


class AuthIdentityRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, provider: AuthProvider, subject: str) -> AuthIdentity | None:
        return self._db.scalar(
            select(AuthIdentity).where(
                AuthIdentity.provider == provider, AuthIdentity.subject == subject
            )
        )

    def get_for_user(self, user_id: UUID, provider: AuthProvider) -> AuthIdentity | None:
        return self._db.scalar(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user_id, AuthIdentity.provider == provider
            )
        )

    def add(self, identity: AuthIdentity) -> AuthIdentity:
        self._db.add(identity)
        self._db.commit()
        self._db.refresh(identity)
        return identity
