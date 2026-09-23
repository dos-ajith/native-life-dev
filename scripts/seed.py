from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.permissions import PermissionName
from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.setting import Setting
from app.models.user import User, UserStatus, UserType
from app.repositories.permission_repository import PermissionRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.user_repository import UserRepository
from app.utils.slug import slugify

DEFAULT_USER_PASSWORD = "Password123!"

ALL_PERMISSION_NAMES = tuple(
    value for key, value in vars(PermissionName).items() if key.isupper()
)

POST_READER_PERMISSIONS = (PermissionName.POST_VIEW,)
POST_ENGAGER_PERMISSIONS = (
    *POST_READER_PERMISSIONS,
    PermissionName.POST_LIKE,
    PermissionName.POST_COMMENT,
    PermissionName.POST_SHARE,
)
POST_AUTHOR_PERMISSIONS = (*POST_ENGAGER_PERMISSIONS, PermissionName.POST_CREATE)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "Super Admin": ALL_PERMISSION_NAMES,
    "Native Admin": ALL_PERMISSION_NAMES,
    "Public Authority": POST_AUTHOR_PERMISSIONS,
    "Business Profile": POST_AUTHOR_PERMISSIONS,
    "Promoter": POST_AUTHOR_PERMISSIONS,
    "Delivery Team Member": POST_ENGAGER_PERMISSIONS,
    "Public User": POST_READER_PERMISSIONS,
}

ROLE_USERS = {
    "Super Admin": ("dev@nativelife.com", UserType.PRIVATE),
    "Native Admin": ("native.admin@nativelife.com", UserType.PRIVATE),
    "Public Authority": ("public.authority@nativelife.com", UserType.PUBLIC),
    "Business Profile": ("business.profile@nativelife.com", UserType.PUBLIC),
    "Promoter": ("promoter@nativelife.com", UserType.PUBLIC),
    "Delivery Team Member": ("delivery.team.member@nativelife.com", UserType.PRIVATE),
}

DEFAULT_SETTINGS = {
    "app_name": "Native Life",
    "app_logo_url": None,
    "app_favicon_url": None,
    "app_site_motto": "Live Native. Live Free.",
    "app_date_format": "DD-MM-YYYY",
    "app_time_format": "hh:mm A",
    "ai_allowed_languages": "all",
}


def _get_or_create_permission(permissions: PermissionRepository, name: str) -> Permission:
    permission = permissions.get_by_name(name)
    if permission is not None:
        return permission
    print(f"Seeded permission: {name}")
    return permissions.add(Permission(name=name))


def seed_roles_and_permissions() -> None:
    db = SessionLocal()
    try:
        permissions = PermissionRepository(db)
        roles = RoleRepository(db)

        seeded_permissions = {
            name: _get_or_create_permission(permissions, name) for name in ALL_PERMISSION_NAMES
        }

        for name, permission_names in ROLE_PERMISSIONS.items():
            slug = slugify(name)
            role = roles.get_by_slug(slug)
            if role is None:
                role = roles.add(Role(name=name, slug=slug, permissions=[]))
                print(f"Seeded role: {name}")

            missing = [
                seeded_permissions[permission_name]
                for permission_name in permission_names
                if seeded_permissions[permission_name] not in role.permissions
            ]
            if missing:
                role.permissions.extend(missing)
                roles.save(role)
                print(f"Assigned {len(missing)} permissions to role: {name}")
    finally:
        db.close()


def seed_role_users() -> None:
    db = SessionLocal()
    try:
        users = UserRepository(db)
        roles = RoleRepository(db)

        for role_name, (email, user_type) in ROLE_USERS.items():
            role = roles.get_by_slug(slugify(role_name))
            if role is None:
                raise RuntimeError(
                    f"Role '{role_name}' does not exist. Run seed_roles_and_permissions first."
                )

            user = users.get_by_email(email)
            if user is None:
                user = User(
                    first_name="Dev",
                    last_name=role_name,
                    email=email,
                    password_hash=hash_password(DEFAULT_USER_PASSWORD),
                    status=UserStatus.ACTIVE,
                    user_type=user_type,
                    roles=[role],
                )
                users.add(user)
                print(f"Seeded user for role '{role_name}': {email} / {DEFAULT_USER_PASSWORD}")
                continue

            if role not in user.roles:
                user.roles.append(role)
                users.save(user)
                print(f"Assigned role '{role_name}' to existing user: {email}")
            else:
                print(f"User already has role '{role_name}': {email}")
    finally:
        db.close()


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
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles_and_permissions()
    seed_role_users()
    seed_settings()
