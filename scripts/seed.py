import json
from uuid import uuid4

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.permissions import PermissionName, RoleName, RoleSlug
from app.core.security import hash_password
from app.models.category import Category, CategoryStatus
from app.models.deal import DEALS_ROOT_CATEGORY_NAME
from app.models.permission import Permission
from app.models.role import Role
from app.models.setting import Setting
from app.models.user import User, UserStatus, UserType
from app.repositories.category_repository import CategoryRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.user_repository import UserRepository
from app.services.business_category_service import BusinessCategoryService
from app.services.category_service import build_category_slug
from app.services.deal_settings_service import (
    DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY,
    DEAL_ACCEPTING_ROLES_SETTING_KEY,
    InvalidDealSettingError,
    parse_accepting_role_slugs,
    resolve_accepting_roles,
)
from app.services.delivery_access_service import (
    DELIVERY_SETTINGS_ROLES_SETTING_KEY,
    InvalidDeliveryRolesError,
    parse_delivery_role_slugs,
    resolve_delivery_roles,
)
from app.services.delivery_timeout_service import (
    DEFAULT_DELIVERY_CLAIM_MINUTES,
    DEFAULT_DELIVERY_RESPONSE_MINUTES,
    DELIVERY_CLAIM_MINUTES_SETTING_KEY,
    DELIVERY_RESPONSE_MINUTES_SETTING_KEY,
)
from app.services.email_service import MANDRILL_ENABLED_SETTING_KEY

DEFAULT_USER_PASSWORD = "Password123!"

ALL_PERMISSION_NAMES = tuple(value for key, value in vars(PermissionName).items() if key.isupper())

MOBILE_ACCOUNT_PERMISSIONS = (
    PermissionName.POST_VIEW,
    PermissionName.PAGE_READ,
    PermissionName.POST_CREATE,
    PermissionName.POST_LIKE,
    PermissionName.POST_COMMENT,
    PermissionName.POST_SHARE,
    PermissionName.POST_SAVE,
    PermissionName.LOST_FOUND_VIEW,
    PermissionName.LOST_FOUND_CREATE,
    PermissionName.EVENTS_VIEW,
    PermissionName.EVENTS_CREATE,
    PermissionName.DEAL_CREATE,
    PermissionName.CATEGORY_SUGGEST,
    PermissionName.NATIVE_PLACE_SUGGEST,
    PermissionName.ROLE_UPGRADE_REQUEST_CREATE,
    PermissionName.ROLE_UPGRADE_REQUEST_VIEW_OWN,
)

NATIVE_ADMIN_PERMISSIONS = (
    PermissionName.POST_VIEW,
    PermissionName.POST_CREATE_ANY,
    PermissionName.POST_VIEW_ANY,
    PermissionName.POST_BLOCK,
    PermissionName.PAGE_READ,
    PermissionName.USER_VIEW,
    PermissionName.LOST_FOUND_VIEW,
    PermissionName.EVENTS_VIEW,
    PermissionName.EVENTS_UPDATE_ANY,
    PermissionName.EVENTS_DELETE_ANY,
    PermissionName.EVENTS_FEATURE,
    PermissionName.ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER,
    PermissionName.COMMUNITY_VIEW_PENDING,
    PermissionName.COMMUNITY_APPROVE,
    PermissionName.COMMUNITY_REJECT,
    PermissionName.BUSINESS_REVIEW,
    PermissionName.BUSINESS_ESCALATE,
    PermissionName.BUSINESS_CREATE_ANY,
)

ROLE_DEFINITIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    RoleSlug.SUPER_ADMIN: (RoleName.SUPER_ADMIN, ALL_PERMISSION_NAMES),
    RoleSlug.NATIVE_ADMIN: (RoleName.NATIVE_ADMIN, NATIVE_ADMIN_PERMISSIONS),
    RoleSlug.INDIVIDUAL_USER: (RoleName.INDIVIDUAL_USER, MOBILE_ACCOUNT_PERMISSIONS),
    RoleSlug.PROMOTER: (
        RoleName.PROMOTER,
        (*MOBILE_ACCOUNT_PERMISSIONS, PermissionName.BUSINESS_SEARCH),
    ),
    RoleSlug.CLUB_COMMUNITY: (
        RoleName.CLUB_COMMUNITY,
        (*MOBILE_ACCOUNT_PERMISSIONS, PermissionName.COMMUNITY_CREATE),
    ),
    RoleSlug.BUSINESS_SERVICE_PROVIDER: (
        RoleName.BUSINESS_SERVICE_PROVIDER,
        (*MOBILE_ACCOUNT_PERMISSIONS, PermissionName.BUSINESS_CREATE),
    ),
}

ROLE_USERS: dict[str, tuple[str, UserType, tuple[str, ...]]] = {
    "dev@nativelife.com": ("Super Admin", UserType.PRIVATE, (RoleSlug.SUPER_ADMIN,)),
    "native.admin@nativelife.com": ("Native Admin", UserType.PRIVATE, (RoleSlug.NATIVE_ADMIN,)),
    "individual@nativelife.com": (
        "Individual User",
        UserType.PUBLIC,
        (RoleSlug.INDIVIDUAL_USER,),
    ),
    "promoter@nativelife.com": (
        "Promoter",
        UserType.PUBLIC,
        (RoleSlug.INDIVIDUAL_USER, RoleSlug.PROMOTER),
    ),
    "club.community@nativelife.com": (
        "Club Community",
        UserType.PUBLIC,
        (RoleSlug.INDIVIDUAL_USER, RoleSlug.CLUB_COMMUNITY),
    ),
    "business@nativelife.com": (
        "Business",
        UserType.PUBLIC,
        (RoleSlug.INDIVIDUAL_USER, RoleSlug.BUSINESS_SERVICE_PROVIDER),
    ),
}

LOST_FOUND_ROOT_CATEGORY = "Lost & Found"
LOST_FOUND_CATEGORIES = ("Electronics", "Accessories", "Documents", "Bags", "Pets", "Other")

EVENTS_ROOT_CATEGORY = "Events"
EVENTS_CATEGORIES = ("Festival", "Community", "Celebration", "Activity")
DEAL_CATEGORIES = ("Deal", "Bulk Deal")

DEFAULT_SETTINGS = {
    "app_name": "Native Life",
    "app_logo_url": None,
    "app_favicon_url": None,
    "app_site_motto": "Live Native. Live Free.",
    "app_date_format": "DD-MM-YYYY",
    "app_time_format": "hh:mm A",
    "ai_allowed_languages": "all",
    DEAL_ACCEPTANCE_TIMEOUT_HOURS_SETTING_KEY: "72",
    DELIVERY_RESPONSE_MINUTES_SETTING_KEY: str(DEFAULT_DELIVERY_RESPONSE_MINUTES),
    DELIVERY_CLAIM_MINUTES_SETTING_KEY: str(DEFAULT_DELIVERY_CLAIM_MINUTES),
}

DEFAULT_DEAL_ACCEPTING_ROLE_SLUG = RoleSlug.PROMOTER
DEFAULT_DELIVERY_SETTINGS_ROLE_SLUGS = (RoleSlug.PROMOTER,)


PLUGIN_PERMISSION_PREFIX = "plugin."
PLUGIN_PERMISSION_MIN_SEGMENTS = 3


def _is_plugin_permission(name: str) -> bool:
    return (
        name.startswith(PLUGIN_PERMISSION_PREFIX)
        and len(name.split(".")) >= PLUGIN_PERMISSION_MIN_SEGMENTS
    )


def _get_or_create_permission(permissions: PermissionRepository, name: str) -> Permission:
    permission = permissions.get_by_name(name)
    if permission is not None:
        return permission
    print(f"Seeded permission: {name}")
    return permissions.add(Permission(name=name))


def _sync_role(roles: RoleRepository, slug: str, name: str, permissions: list[Permission]) -> None:
    role = roles.get_by_slug(slug)
    if role is None:
        roles.add(Role(name=name, slug=slug, permissions=permissions))
        print(f"Seeded role: {name}")
        return
    changed = False
    if role.name != name:
        print(f"Renamed role '{role.name}' to '{name}'")
        role.name = name
        changed = True
    desired = {permission.id: permission for permission in permissions}
    for permission in role.permissions:
        if _is_plugin_permission(permission.name):
            desired.setdefault(permission.id, permission)
    if {permission.id for permission in role.permissions} != set(desired):
        print(f"Synced {len(desired)} permissions for role: {name}")
        role.permissions = list(desired.values())
        changed = True
    if changed:
        roles.save(role)


def _remove_obsolete_roles(roles: RoleRepository) -> None:
    for role in roles.list_all():
        if role.slug in ROLE_DEFINITIONS:
            continue
        holders = roles.count_holders(role.id)
        if holders:
            raise RuntimeError(
                f"Obsolete role '{role.slug}' is still assigned to {holders} user(s). "
                "Run 'alembic upgrade head' to migrate them before seeding."
            )
        roles.delete(role)
        print(f"Removed obsolete role: {role.slug}")


def seed_roles_and_permissions() -> None:
    db = SessionLocal()
    try:
        permissions = PermissionRepository(db)
        roles = RoleRepository(db)

        seeded_permissions = {
            name: _get_or_create_permission(permissions, name) for name in ALL_PERMISSION_NAMES
        }

        _remove_obsolete_roles(roles)
        for slug, (name, permission_names) in ROLE_DEFINITIONS.items():
            granted = [seeded_permissions[permission_name] for permission_name in permission_names]
            _sync_role(roles, slug, name, granted)
    finally:
        db.close()


def seed_role_users() -> None:
    db = SessionLocal()
    try:
        users = UserRepository(db)
        roles = RoleRepository(db)

        for email, (last_name, user_type, role_slugs) in ROLE_USERS.items():
            required = []
            for slug in role_slugs:
                role = roles.get_by_slug(slug)
                if role is None:
                    raise RuntimeError(
                        f"Role '{slug}' does not exist. Run seed_roles_and_permissions first."
                    )
                required.append(role)

            user = users.get_by_email(email)
            if user is None:
                users.add(
                    User(
                        first_name="Dev",
                        last_name=last_name,
                        email=email,
                        password_hash=hash_password(DEFAULT_USER_PASSWORD),
                        status=UserStatus.ACTIVE,
                        user_type=user_type,
                        roles=required,
                    )
                )
                print(f"Seeded user: {email} / {DEFAULT_USER_PASSWORD}")
                continue

            missing = [role for role in required if role not in user.roles]
            if missing:
                user.roles.extend(missing)
                users.save(user)
                print(f"Assigned {len(missing)} role(s) to existing user: {email}")
    finally:
        db.close()


def _get_or_create_category(
    categories: CategoryRepository, parent: Category | None, name: str
) -> Category:
    parent_id = parent.id if parent is not None else None
    existing = categories.find_by_name(parent_id, name)
    if existing is not None:
        return existing
    print(f"Seeded category: {name}")
    category_id = uuid4()
    return categories.add(
        Category(
            id=category_id,
            parent_id=parent_id,
            name=name,
            slug=build_category_slug(categories, name, category_id),
            status=CategoryStatus.PUBLISHED,
            is_active=True,
        )
    )


def seed_lost_found_categories() -> None:
    db = SessionLocal()
    try:
        categories = CategoryRepository(db)
        root = _get_or_create_category(categories, None, LOST_FOUND_ROOT_CATEGORY)
        for name in LOST_FOUND_CATEGORIES:
            _get_or_create_category(categories, root, name)
    finally:
        db.close()


def seed_event_categories() -> None:
    db = SessionLocal()
    try:
        categories = CategoryRepository(db)
        root = _get_or_create_category(categories, None, EVENTS_ROOT_CATEGORY)
        for name in EVENTS_CATEGORIES:
            _get_or_create_category(categories, root, name)
    finally:
        db.close()


def seed_deal_categories() -> None:
    db = SessionLocal()
    try:
        categories = CategoryRepository(db)
        root = _get_or_create_category(categories, None, DEALS_ROOT_CATEGORY_NAME)
        for name in DEAL_CATEGORIES:
            _get_or_create_category(categories, root, name)
    finally:
        db.close()


def seed_business_categories() -> None:
    db = SessionLocal()
    try:
        for category in BusinessCategoryService(db).seed():
            print(f"Seeded category: {category.name} ({category.slug})")
    finally:
        db.close()


def seed_deal_accepting_roles() -> None:
    db = SessionLocal()
    try:
        settings = SettingRepository(db)
        roles = RoleRepository(db)
        existing = settings.get_by_key(DEAL_ACCEPTING_ROLES_SETTING_KEY)
        if existing is not None:
            _warn_if_invalid_accepting_roles(roles, existing.value)
            return
        role = roles.get_by_slug(DEFAULT_DEAL_ACCEPTING_ROLE_SLUG)
        if role is None:
            raise RuntimeError(
                f"Role '{DEFAULT_DEAL_ACCEPTING_ROLE_SLUG}' does not exist, so "
                f"'{DEAL_ACCEPTING_ROLES_SETTING_KEY}' was not created. Run "
                "seed_roles_and_permissions first; deal submission stays unavailable until "
                "the setting is configured."
            )
        value = json.dumps([role.slug])
        resolve_accepting_roles(roles, parse_accepting_role_slugs(value))
        settings.add(Setting(key=DEAL_ACCEPTING_ROLES_SETTING_KEY, value=value))
        print(f"Seeded setting: {DEAL_ACCEPTING_ROLES_SETTING_KEY} = {value}")
    finally:
        db.close()


def _warn_if_invalid_accepting_roles(roles: RoleRepository, value: str | None) -> None:
    try:
        resolve_accepting_roles(roles, parse_accepting_role_slugs(value))
    except InvalidDealSettingError as exc:
        print(f"Warning: existing '{DEAL_ACCEPTING_ROLES_SETTING_KEY}' is invalid: {exc}")


def _get_or_create_setting(settings: SettingRepository, key: str, value: str | None) -> Setting:
    setting = settings.get_by_key(key)
    if setting is not None:
        return setting
    print(f"Seeded setting: {key}")
    return settings.add(Setting(key=key, value=value))


def seed_settings() -> None:
    db = SessionLocal()
    try:
        settings = SettingRepository(db)
        for key, value in DEFAULT_SETTINGS.items():
            _get_or_create_setting(settings, key, value)
        _get_or_create_setting(settings, "app_timezone", get_settings().default_timezone)
        _get_or_create_setting(
            settings,
            MANDRILL_ENABLED_SETTING_KEY,
            "true" if get_settings().mandrill_enabled else "false",
        )
    finally:
        db.close()


def seed_delivery_settings_roles() -> None:
    db = SessionLocal()
    try:
        settings = SettingRepository(db)
        roles = RoleRepository(db)
        existing = settings.get_by_key(DELIVERY_SETTINGS_ROLES_SETTING_KEY)
        if existing is not None:
            try:
                resolve_delivery_roles(roles, parse_delivery_role_slugs(existing.value))
            except InvalidDeliveryRolesError as exc:
                print(
                    f"Warning: existing '{DELIVERY_SETTINGS_ROLES_SETTING_KEY}' is invalid: {exc}"
                )
            return
        value = json.dumps(list(DEFAULT_DELIVERY_SETTINGS_ROLE_SLUGS))
        resolve_delivery_roles(roles, parse_delivery_role_slugs(value))
        settings.add(Setting(key=DELIVERY_SETTINGS_ROLES_SETTING_KEY, value=value))
        print(f"Seeded setting: {DELIVERY_SETTINGS_ROLES_SETTING_KEY} = {value}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles_and_permissions()
    seed_role_users()
    seed_settings()
    seed_lost_found_categories()
    seed_event_categories()
    seed_deal_categories()
    seed_business_categories()
    seed_deal_accepting_roles()
    seed_delivery_settings_roles()
