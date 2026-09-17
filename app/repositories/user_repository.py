from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.pagination import PaginationParams


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        return self._db.scalar(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )

    def get_by_phone(self, phone: str) -> User | None:
        return self._db.scalar(
            select(User).where(User.phone == phone, User.deleted_at.is_(None))
        )

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._db.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )

    def list(self, params: PaginationParams) -> tuple[list[User], int]:
        not_deleted = User.deleted_at.is_(None)
        total = self._db.scalar(select(func.count()).select_from(User).where(not_deleted)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(User)
            .where(not_deleted)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, user: User) -> User:
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def save(self, user: User) -> User:
        self._db.commit()
        self._db.refresh(user)
        return user

    def soft_delete(self, user: User) -> None:
        user.deleted_at = datetime.now(UTC)
        self._db.commit()
