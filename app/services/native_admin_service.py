from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.messages import NativePlaceMessages, UserMessages
from app.core.permissions import RoleSlug
from app.core.security import hash_password
from app.models.gis_village import GisVillage
from app.models.user import User, UserStatus, UserType
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "native_place"


class NativeAdminService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._villages = GisVillageRepository(db)
        self._users = UserRepository(db)
        self._roles = RoleRepository(db)
        self._activity_logs = ActivityLogService(db)

    def create(self, village_id: UUID, payload: UserCreate, actor: User) -> tuple[GisVillage, User]:
        village = self._get_village(village_id)
        if village.native_admin_id is not None:
            raise ConflictError(NativePlaceMessages.ADMIN_ALREADY_ASSIGNED)
        self._ensure_contact_available(payload)
        role = self._roles.get_by_slug(RoleSlug.NATIVE_ADMIN)
        if role is None:
            raise ServiceUnavailableError(NativePlaceMessages.ADMIN_ROLE_MISSING)
        admin = self._users.stage(
            User(
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=payload.email,
                phone=payload.phone,
                password_hash=hash_password(payload.password),
                gender=payload.gender,
                date_of_birth=payload.date_of_birth,
                status=UserStatus.ACTIVE,
                user_type=UserType.PRIVATE,
                roles=[role],
                created_by=actor.id,
            )
        )
        village.native_admin_id = admin.id
        try:
            self._villages.save(village)
        except IntegrityError:
            self._db.rollback()
            raise ConflictError(NativePlaceMessages.ADMIN_ALREADY_ASSIGNED) from None
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_CREATED,
            entity_type="user",
            entity_id=admin.id,
            metadata={
                "email": admin.email,
                "user_type": admin.user_type.value,
                "role_ids": [str(role.id)],
            },
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.NATIVE_ADMIN_ASSIGNED,
            entity_type=ENTITY_TYPE,
            entity_id=village.id,
            metadata={"admin_id": str(admin.id)},
        )
        return village, admin

    def remove(self, village_id: UUID, actor: User) -> None:
        village = self._get_village(village_id)
        if village.native_admin_id is None:
            raise NotFoundError(NativePlaceMessages.NO_ADMIN)
        admin = self._users.get_by_id(village.native_admin_id)
        removed_admin_id = village.native_admin_id
        village.native_admin_id = None
        if admin is not None:
            admin.roles = [role for role in admin.roles if role.slug != RoleSlug.NATIVE_ADMIN]
        self._villages.save(village)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.NATIVE_ADMIN_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=village.id,
            metadata={"admin_id": str(removed_admin_id)},
        )

    def _get_village(self, village_id: UUID) -> GisVillage:
        village = self._villages.get_by_id_without_geometry(village_id)
        if village is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)
        return village

    def _ensure_contact_available(self, payload: UserCreate) -> None:
        if self._users.get_by_email(payload.email) is not None:
            raise BusinessRuleError(UserMessages.EMAIL_TAKEN)
        if payload.phone is not None and self._users.get_by_phone(payload.phone) is not None:
            raise BusinessRuleError(UserMessages.PHONE_TAKEN)
