from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import hash_password
from app.models.user import User, UserStatus, UserType
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserCreate, UserSelfUpdate, UserUpdate


class UserService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)

    def create(self, payload: UserCreate) -> User:
        return self._create(payload, UserType.PRIVATE)

    def register(self, payload: UserCreate) -> User:
        return self._create(payload, UserType.PUBLIC)

    def _create(self, payload: UserCreate, user_type: UserType) -> User:
        if self._users.get_by_email(payload.email) is not None:
            raise BusinessRuleError("Email is already registered")
        if payload.phone is not None and self._users.get_by_phone(payload.phone) is not None:
            raise BusinessRuleError("Phone number is already registered")
        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE,
            user_type=user_type,
        )
        return self._users.add(user)

    def get(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def list(self, params: PaginationParams) -> tuple[list[User], int]:
        return self._users.list(params)

    def delete(self, user_id: UUID, acting_user: User) -> None:
        if user_id == acting_user.id:
            raise BusinessRuleError("Cannot delete your own account")
        user = self.get(user_id)
        self._users.soft_delete(user)

    def update(self, user_id: UUID, payload: UserUpdate) -> User:
        user = self.get(user_id)
        data = payload.model_dump(exclude_none=True)
        self._check_uniqueness(user, data)
        for field, value in data.items():
            setattr(user, field, value)
        return self._users.save(user)

    def update_self(self, user: User, payload: UserSelfUpdate) -> User:
        data = payload.model_dump(exclude_none=True)
        self._check_uniqueness(user, data)
        for field, value in data.items():
            setattr(user, field, value)
        return self._users.save(user)

    def _check_uniqueness(self, user: User, data: dict[str, Any]) -> None:
        email = data.get("email")
        if email is not None and email != user.email and self._users.get_by_email(email):
            raise BusinessRuleError("Email is already registered")
        phone = data.get("phone")
        if phone is not None and phone != user.phone and self._users.get_by_phone(phone):
            raise BusinessRuleError("Phone number is already registered")
