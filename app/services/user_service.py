from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError, ServiceUnavailableError
from app.core.messages import UserMessages
from app.core.permissions import RoleSlug
from app.core.security import hash_password
from app.core.storage import delete_media_file, save_profile_image
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserCreate, UserSelfUpdate, UserUpdate
from app.services.activity_log_service import ActivityLogService


class UserService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)
        self._roles = RoleRepository(db)
        self._activity_logs = ActivityLogService(db)

    def create(
        self,
        payload: UserCreate,
        acting_user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
        image: UploadFile | None = None,
        upload_dir: str | None = None,
        role_ids: list[UUID] | None = None,
    ) -> User:
        roles = self._resolve_roles(role_ids) if role_ids else []
        user = self._create(
            payload,
            UserType.PRIVATE,
            roles=roles,
            created_by=acting_user.id,
            image=image,
            upload_dir=upload_dir,
        )
        self._activity_logs.log(
            actor=acting_user,
            action=ActivityAction.USER_CREATED,
            entity_type="user",
            entity_id=user.id,
            metadata={
                "email": user.email,
                "user_type": user.user_type.value,
                "role_ids": [str(role.id) for role in roles],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return user

    def register(
        self,
        payload: UserCreate,
        ip_address: str | None = None,
        user_agent: str | None = None,
        image: UploadFile | None = None,
        upload_dir: str | None = None,
    ) -> User:
        default_role = self._roles.get_by_slug(RoleSlug.PUBLIC_AUTHORITY)
        if default_role is None:
            raise ServiceUnavailableError(UserMessages.DEFAULT_ROLE_MISSING)
        user = self._create(
            payload,
            UserType.PUBLIC,
            roles=[default_role],
            image=image,
            upload_dir=upload_dir,
        )
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.USER_CREATED,
            entity_type="user",
            entity_id=user.id,
            metadata={"email": user.email, "user_type": user.user_type.value, "source": "self"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return user

    def _create(
        self,
        payload: UserCreate,
        user_type: UserType,
        roles: list[Role] | None = None,
        created_by: UUID | None = None,
        image: UploadFile | None = None,
        upload_dir: str | None = None,
    ) -> User:
        if self._users.get_by_email(payload.email) is not None:
            raise BusinessRuleError(UserMessages.EMAIL_TAKEN)
        if payload.phone is not None and self._users.get_by_phone(payload.phone) is not None:
            raise BusinessRuleError(UserMessages.PHONE_TAKEN)
        profile_image_url = None
        if image is not None:
            assert upload_dir is not None
            profile_image_url = save_profile_image(image, upload_dir)
        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE,
            user_type=user_type,
            roles=roles or [],
            created_by=created_by,
            profile_image_url=profile_image_url,
        )
        return self._users.add(user)

    def get(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        return user

    def _resolve_roles(self, role_ids: list[UUID]) -> list[Role]:
        roles = self._roles.get_by_ids(role_ids)
        missing_ids = set(role_ids) - {role.id for role in roles}
        if missing_ids:
            names = ", ".join(str(role_id) for role_id in missing_ids)
            raise BusinessRuleError(UserMessages.UNKNOWN_ROLE_IDS.format(ids=names))
        return roles

    def assign_roles(self, user_id: UUID, role_ids: list[UUID], actor: User) -> User:
        user = self.get(user_id)
        roles = self._resolve_roles(role_ids)
        previous_role_ids = {role.id for role in user.roles}
        new_role_ids = {role.id for role in roles}
        added_roles = [role for role in roles if role.id not in previous_role_ids]
        removed_roles = [role for role in user.roles if role.id not in new_role_ids]
        user.roles = roles
        saved_user = self._users.save(user)
        for role in added_roles:
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.ROLE_ASSIGNED,
                entity_type="user",
                entity_id=user.id,
                metadata={"role_id": str(role.id), "role_name": role.name},
            )
        for role in removed_roles:
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.ROLE_REMOVED,
                entity_type="user",
                entity_id=user.id,
                metadata={"role_id": str(role.id), "role_name": role.name},
            )
        return saved_user

    def list(self, params: PaginationParams) -> tuple[list[User], int]:
        return self._users.list(params)

    def delete(self, user_id: UUID, acting_user: User) -> None:
        if user_id == acting_user.id:
            raise BusinessRuleError(UserMessages.CANNOT_DELETE_SELF)
        user = self.get(user_id)
        self._users.soft_delete(user)
        self._activity_logs.log(
            actor=acting_user,
            action=ActivityAction.USER_DELETED,
            entity_type="user",
            entity_id=user.id,
            metadata={"email": user.email},
        )

    def update(self, user_id: UUID, payload: UserUpdate, actor: User) -> User:
        user = self.get(user_id)
        data = payload.model_dump(exclude_none=True)
        self._check_uniqueness(user, data)
        for field, value in data.items():
            setattr(user, field, value)
        saved_user = self._users.save(user)
        self._log_updated(saved_user, actor, list(data.keys()))
        return saved_user

    def update_self(self, user: User, payload: UserSelfUpdate) -> User:
        data = payload.model_dump(exclude_none=True)
        self._check_uniqueness(user, data)
        for field, value in data.items():
            setattr(user, field, value)
        saved_user = self._users.save(user)
        self._log_updated(saved_user, saved_user, list(data.keys()))
        return saved_user

    def _log_updated(self, user: User, actor: User, updated_fields: Sequence[str]) -> None:
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_UPDATED,
            entity_type="user",
            entity_id=user.id,
            metadata={"updated_fields": list(updated_fields)},
        )

    def update_image(self, user: User, image: UploadFile, upload_dir: str) -> User:
        previous_url = user.profile_image_url
        user.profile_image_url = save_profile_image(image, upload_dir)
        saved = self._users.save(user)
        if previous_url is not None:
            delete_media_file(previous_url, upload_dir)
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
