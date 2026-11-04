import json
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ServiceUnavailableError
from app.core.messages import DealMessages
from app.core.permissions import VERIFIED_ACCOUNT_ROLE_SLUGS
from app.models.role import Role
from app.repositories.role_repository import RoleRepository
from app.repositories.setting_repository import SettingRepository

DEAL_ACCEPTING_ROLES_SETTING_KEY = "deal_accepting_roles"
DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY = "deal_acceptance_timeout_hours"
DEAL_SETTING_KEYS = frozenset(
    {DEAL_ACCEPTING_ROLES_SETTING_KEY, DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY}
)
DEAL_ACCEPTING_ROLES_LIMIT = 1
MIN_DEAL_ACCEPTANCE_TIMEOUT_HOURS = 1
MAX_DEAL_ACCEPTANCE_TIMEOUT_HOURS = 720

logger = logging.getLogger("app.deals")


class InvalidDealSettingError(ValueError):
    pass


def parse_accepting_role_slugs(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        raise InvalidDealSettingError(DealMessages.ACCEPTING_ROLES_INVALID)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidDealSettingError(DealMessages.ACCEPTING_ROLES_INVALID) from exc
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise InvalidDealSettingError(DealMessages.ACCEPTING_ROLES_INVALID)
    slugs = [item.strip() for item in value]
    if len(set(slugs)) != len(slugs):
        raise InvalidDealSettingError(DealMessages.ACCEPTING_ROLES_INVALID)
    if len(slugs) != DEAL_ACCEPTING_ROLES_LIMIT:
        raise InvalidDealSettingError(
            DealMessages.ACCEPTING_ROLES_COUNT.format(limit=DEAL_ACCEPTING_ROLES_LIMIT)
        )
    return slugs


def parse_acceptance_timeout_hours(raw: str | None) -> int:
    message = DealMessages.ACCEPTANCE_TIMEOUT_INVALID.format(
        minimum=MIN_DEAL_ACCEPTANCE_TIMEOUT_HOURS, maximum=MAX_DEAL_ACCEPTANCE_TIMEOUT_HOURS
    )
    if raw is None or not raw.strip().isdigit():
        raise InvalidDealSettingError(message)
    hours = int(raw.strip())
    if not MIN_DEAL_ACCEPTANCE_TIMEOUT_HOURS <= hours <= MAX_DEAL_ACCEPTANCE_TIMEOUT_HOURS:
        raise InvalidDealSettingError(message)
    return hours


def resolve_accepting_roles(roles: RoleRepository, slugs: list[str]) -> list[Role]:
    resolved = []
    for slug in slugs:
        role = roles.get_by_slug(slug)
        if role is None:
            raise InvalidDealSettingError(DealMessages.ACCEPTING_ROLE_UNKNOWN.format(slug=slug))
        if role.slug not in VERIFIED_ACCOUNT_ROLE_SLUGS:
            raise InvalidDealSettingError(
                DealMessages.ACCEPTING_ROLE_NOT_VERIFIABLE.format(slug=slug)
            )
        resolved.append(role)
    return resolved


class DealSettingsService:
    def __init__(self, db: Session) -> None:
        self._settings = SettingRepository(db)
        self._roles = RoleRepository(db)

    def accepting_roles(self) -> list[Role]:
        try:
            return resolve_accepting_roles(
                self._roles, parse_accepting_role_slugs(self._raw(DEAL_ACCEPTING_ROLES_SETTING_KEY))
            )
        except InvalidDealSettingError as exc:
            self._report_misconfiguration(DEAL_ACCEPTING_ROLES_SETTING_KEY, exc)
            raise ServiceUnavailableError(DealMessages.ACCEPTANCE_NOT_CONFIGURED) from exc

    def acceptance_timeout(self) -> timedelta:
        try:
            hours = parse_acceptance_timeout_hours(
                self._raw(DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY)
            )
        except InvalidDealSettingError as exc:
            self._report_misconfiguration(DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY, exc)
            raise ServiceUnavailableError(DealMessages.ACCEPTANCE_NOT_CONFIGURED) from exc
        return timedelta(hours=hours)

    def ensure_valid(self, key: str, value: str | None) -> None:
        try:
            if key == DEAL_ACCEPTING_ROLES_SETTING_KEY:
                resolve_accepting_roles(self._roles, parse_accepting_role_slugs(value))
            elif key == DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY:
                parse_acceptance_timeout_hours(value)
        except InvalidDealSettingError as exc:
            raise BusinessRuleError(str(exc)) from exc

    def _raw(self, key: str) -> str | None:
        setting = self._settings.get_by_key(key)
        return setting.value if setting is not None else None

    @staticmethod
    def _report_misconfiguration(key: str, exc: InvalidDealSettingError) -> None:
        logger.error("Deal setting '%s' is missing or invalid: %s", key, exc)
