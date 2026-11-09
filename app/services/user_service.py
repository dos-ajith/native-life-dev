from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.messages import UserMessages
from app.core.permissions import ADMIN_ROLE_SLUGS, RoleSlug
from app.core.security import hash_password
from app.core.storage import delete_media_file, save_profile_image
from app.core.timezone import app_now
from app.models.auth_identity import AuthIdentity
from app.models.role import Role
from app.models.user import User, UserGender, UserStatus, UserType
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserDiscoveryRow, UserProfileRow, UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user import (
    UserCreate,
    UserDiscoveryRead,
    UserProfileRead,
    UserSelfUpdate,
    UserUpdate,
)
from app.schemas.user_follow import FollowRelationship
from app.services.account_role_status_service import AccountRoleStatusService
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import is_super_admin
from app.services.email_domain_policy import ensure_email_domain_allowed
from app.services.email_verification_service import EmailVerificationService


@dataclass(frozen=True)
class VerifiedAccount:
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    identities: Sequence[AuthIdentity] = ()
    gender: UserGender | None = None
    date_of_birth: date | None = None


class UserService:
    def __init__(self, db: Session) -> None:
        self._db = db
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
        self._ensure_can_change_roles(acting_user, [], roles)
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
        settings: Settings,
        background_tasks: BackgroundTasks,
        ip_address: str | None = None,
        user_agent: str | None = None,
        image: UploadFile | None = None,
        upload_dir: str | None = None,
    ) -> User:
        ensure_email_domain_allowed(payload.email, settings)
        user = self._create(
            payload,
            UserType.PUBLIC,
            roles=[self._default_account_role()],
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
        EmailVerificationService(self._db, settings).issue_for_registration(user, background_tasks)
        return user

    def create_verified_account(
        self,
        account: VerifiedAccount,
        source: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        now = app_now()
        user = User(
            first_name=account.first_name,
            last_name=account.last_name,
            email=account.email,
            email_verified_at=now if account.email is not None else None,
            phone=account.phone,
            phone_verified_at=now if account.phone is not None else None,
            gender=account.gender,
            date_of_birth=account.date_of_birth,
            terms_accepted_at=now,
            status=UserStatus.ACTIVE,
            user_type=UserType.PUBLIC,
            roles=[self._default_account_role()],
            auth_identities=list(account.identities),
        )
        saved = self._users.add(user)
        self._activity_logs.log(
            actor=saved,
            action=ActivityAction.USER_CREATED,
            entity_type="user",
            entity_id=saved.id,
            metadata={"user_type": saved.user_type.value, "source": source},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return saved

    def _default_account_role(self) -> Role:
        default_role = self._roles.get_by_slug(RoleSlug.INDIVIDUAL_USER)
        if default_role is None:
            raise ServiceUnavailableError(UserMessages.DEFAULT_ROLE_MISSING)
        return default_role

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
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
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
        self._ensure_can_modify(actor, user)
        self._ensure_can_change_roles(actor, user.roles, roles)
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

    def list_discoverable(
        self, viewer: User, search: str | None, params: PaginationParams
    ) -> tuple[Sequence[UserDiscoveryRead], int]:
        rows, total = self._users.list_discoverable(viewer.id, search and search.strip(), params)
        return [self._to_discovery_read(row) for row in rows], total

    def list_connects(
        self, viewer: User, params: PaginationParams
    ) -> tuple[Sequence[UserDiscoveryRead], int]:
        rows, total = self._users.list_discoverable(viewer.id, None, params, exclude_following=True)
        return [self._to_discovery_read(row) for row in rows], total

    def get_profile(self, viewer: User, user_id: UUID) -> UserProfileRead:
        row = self._users.get_profile(viewer.id, user_id)
        if row is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        profile = self._to_profile_read(row)
        account_role = AccountRoleStatusService(self._db).describe_public(user_id)
        return profile.model_copy(update={"account_role": account_role})

    @staticmethod
    def _follow_status(is_following: bool, is_requested: bool) -> FollowRelationship:
        if is_following:
            return FollowRelationship.ACCEPTED
        if is_requested:
            return FollowRelationship.PENDING
        return FollowRelationship.NONE

    @staticmethod
    def _to_profile_read(row: UserProfileRow) -> UserProfileRead:
        return UserProfileRead(
            id=row.id,
            name=f"{row.first_name} {row.last_name}",
            profile_image_url=row.profile_image_url,
            followers_count=row.followers_count,
            following_count=row.following_count,
            posts_count=row.posts_count,
            is_following=row.is_following,
            is_followed_by=row.is_followed_by,
            follow_status=UserService._follow_status(row.is_following, row.is_requested),
        )

    @staticmethod
    def _to_discovery_read(row: UserDiscoveryRow) -> UserDiscoveryRead:
        follow_status = UserService._follow_status(row.is_following, row.is_requested)
        return UserDiscoveryRead(
            id=row.id,
            name=f"{row.first_name} {row.last_name}",
            profile_image_url=row.profile_image_url,
            followers_count=row.followers_count,
            following_count=row.following_count,
            is_following=row.is_following,
            follow_status=follow_status,
            shares_native_place=row.shares_native_place,
        )

    def delete(self, user_id: UUID, acting_user: User) -> None:
        if user_id == acting_user.id:
            raise BusinessRuleError(UserMessages.CANNOT_DELETE_SELF)
        user = self.get(user_id)
        self._ensure_can_modify(acting_user, user)
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
        self._ensure_can_modify(actor, user)
        data = payload.model_dump(exclude_none=True)
        self._check_uniqueness(user, data)
        if data.get("phone", user.phone) != user.phone:
            user.phone_verified_at = None
        for field, value in data.items():
            setattr(user, field, value)
        saved_user = self._users.save(user)
        self._log_updated(saved_user, actor, list(data.keys()))
        return saved_user

    def update_self(self, user: User, payload: UserSelfUpdate) -> User:
        data = payload.model_dump(exclude_none=True)
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

    def update_image_for(
        self, user_id: UUID, image: UploadFile, upload_dir: str, actor: User
    ) -> User:
        user = self.get(user_id)
        self._ensure_can_modify(actor, user)
        return self.update_image(user, image, upload_dir)

    @staticmethod
    def _ensure_can_modify(actor: User, target: User) -> None:
        if is_super_admin(target) and not is_super_admin(actor):
            raise AuthorizationError(UserMessages.SUPER_ADMIN_PROTECTED)

    @staticmethod
    def _ensure_can_change_roles(
        actor: User, previous: Sequence[Role], new: Sequence[Role]
    ) -> None:
        changed = {role.slug for role in previous} ^ {role.slug for role in new}
        if RoleSlug.NATIVE_ADMIN in changed:
            raise BusinessRuleError(UserMessages.NATIVE_ADMIN_ROLE_MANAGED_BY_NATIVE_PLACE)
        if len(new) > 1:
            raise BusinessRuleError(UserMessages.SINGLE_ROLE_ONLY)
        if is_super_admin(actor):
            return
        if changed & ADMIN_ROLE_SLUGS:
            raise AuthorizationError(UserMessages.ADMIN_ROLE_CHANGE_FORBIDDEN)

    def _check_uniqueness(self, user: User, data: dict[str, Any]) -> None:
        email = data.get("email")
        if email is not None and email != user.email and self._users.get_by_email(email):
            raise BusinessRuleError(UserMessages.EMAIL_TAKEN)
        phone = data.get("phone")
        if phone is not None and phone != user.phone and self._users.get_by_phone(phone):
            raise BusinessRuleError(UserMessages.PHONE_TAKEN)
