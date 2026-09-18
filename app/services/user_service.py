from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError, ServiceUnavailableError
from app.core.messages import UserMessages
from app.core.security import hash_password
from app.core.storage import delete_profile_image, save_profile_image
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserCreate, UserSelfUpdate, UserUpdate

DEFAULT_PUBLIC_ROLE_SLUG = "public-user"


class UserService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)
        self._roles = RoleRepository(db)

    def create(self, payload: UserCreate) -> User:
        return self._create(payload, UserType.PRIVATE)

    def register(self, payload: UserCreate) -> User:
        default_role = self._roles.get_by_slug(DEFAULT_PUBLIC_ROLE_SLUG)
        if default_role is None:
            raise ServiceUnavailableError(UserMessages.DEFAULT_ROLE_MISSING)
        return self._create(payload, UserType.PUBLIC, roles=[default_role])

    def _create(
        self, payload: UserCreate, user_type: UserType, roles: list[Role] | None = None
    ) -> User:
        if self._users.get_by_email(payload.email) is not None:
            raise BusinessRuleError(UserMessages.EMAIL_TAKEN)
        if payload.phone is not None and self._users.get_by_phone(payload.phone) is not None:
            raise BusinessRuleError(UserMessages.PHONE_TAKEN)
        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE,
            user_type=user_type,
            roles=roles or [],
        )
        return self._users.add(user)

    def get(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        return user

    def assign_roles(self, user_id: UUID, role_ids: list[UUID]) -> User:
        user = self.get(user_id)
        roles = self._roles.get_by_ids(role_ids)
        missing_ids = set(role_ids) - {role.id for role in roles}
        if missing_ids:
            names = ", ".join(str(role_id) for role_id in missing_ids)
            raise BusinessRuleError(UserMessages.UNKNOWN_ROLE_IDS.format(ids=names))
        user.roles = roles
        return self._users.save(user)

    def list(self, params: PaginationParams) -> tuple[list[User], int]:
        return self._users.list(params)

    def delete(self, user_id: UUID, acting_user: User) -> None:
        if user_id == acting_user.id:
            raise BusinessRuleError(UserMessages.CANNOT_DELETE_SELF)
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

    def update_image(self, user: User, image: UploadFile, upload_dir: str) -> User:
        previous_url = user.profile_image_url
        user.profile_image_url = save_profile_image(image, upload_dir)
        saved = self._users.save(user)
        if previous_url is not None:
            delete_profile_image(previous_url, upload_dir)
        return saved

    def update_image_for(self, user_id: UUID, image: UploadFile, upload_dir: str) -> User:
        return self.update_image(self.get(user_id), image, upload_dir)

    def _check_uniqueness(self, user: User, data: dict[str, Any]) -> None:
        email = data.get("email")
        if email is not None and email != user.email and self._users.get_by_email(email):
            raise BusinessRuleError(UserMessages.EMAIL_TAKEN)
        phone = data.get("phone")
        if phone is not None and phone != user.phone and self._users.get_by_phone(phone):
            raise BusinessRuleError(UserMessages.PHONE_TAKEN)
