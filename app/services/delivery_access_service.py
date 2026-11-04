import json
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ServiceUnavailableError
from app.core.messages import DeliveryMessages
from app.core.permissions import VERIFIED_ACCOUNT_ROLE_SLUGS
from app.models.role import Role
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.user_role_assignment_repository import UserRoleAssignmentRepository

DELIVERY_SETTINGS_ROLES_SETTING_KEY = "delivery_settings_roles"

logger = logging.getLogger("app.deliveries")


class InvalidDeliveryRolesError(ValueError):
    pass


def parse_delivery_role_slugs(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        raise InvalidDeliveryRolesError(DeliveryMessages.ROLES_INVALID)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidDeliveryRolesError(DeliveryMessages.ROLES_INVALID) from exc
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise InvalidDeliveryRolesError(DeliveryMessages.ROLES_INVALID)
    slugs = [item.strip() for item in value]
    if len(set(slugs)) != len(slugs):
        raise InvalidDeliveryRolesError(DeliveryMessages.ROLES_INVALID)
    return slugs


def resolve_delivery_roles(roles: RoleRepository, slugs: list[str]) -> list[Role]:
    resolved = []
    for slug in slugs:
        role = roles.get_by_slug(slug)
        if role is None:
            raise InvalidDeliveryRolesError(DeliveryMessages.ROLE_UNKNOWN.format(slug=slug))
        if role.slug not in VERIFIED_ACCOUNT_ROLE_SLUGS:
            raise InvalidDeliveryRolesError(DeliveryMessages.ROLE_NOT_VERIFIABLE.format(slug=slug))
        resolved.append(role)
    return resolved


class DeliveryAccessService:
    def __init__(self, db: Session) -> None:
        self._settings = SettingRepository(db)
        self._roles = RoleRepository(db)
        self._assignments = UserRoleAssignmentRepository(db)

    def roles(self) -> list[Role]:
        setting = self._settings.get_by_key(DELIVERY_SETTINGS_ROLES_SETTING_KEY)
        try:
            return resolve_delivery_roles(
                self._roles, parse_delivery_role_slugs(setting.value if setting else None)
            )
        except InvalidDeliveryRolesError as exc:
            logger.error(
                "Setting '%s' is missing or invalid: %s", DELIVERY_SETTINGS_ROLES_SETTING_KEY, exc
            )
            raise ServiceUnavailableError(DeliveryMessages.ACCESS_NOT_CONFIGURED) from exc

    def holds_role(self, user: User) -> bool:
        role_ids = {role.id for role in self.roles()}
        return any(
            assignment.role_id in role_ids and assignment.verified_at is not None
            for assignment in self._assignments.list_for_users([user.id])
        )

    def ensure_valid(self, value: str | None) -> None:
        try:
            resolve_delivery_roles(self._roles, parse_delivery_role_slugs(value))
        except InvalidDeliveryRolesError as exc:
            raise BusinessRuleError(str(exc)) from exc
