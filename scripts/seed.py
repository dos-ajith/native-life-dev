from app.core.database import SessionLocal
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

PERMISSION_NAMES = ("user.view", "user.create", "user.update", "user.delete")
FULL_PERMISSIONS_ROLE_SLUG = "super-admin"

ROLE_USERS = {
    "Super Admin": ("dev@nativelife.com", UserType.PRIVATE),
    "Native Admin": ("native.admin@nativelife.com", UserType.PRIVATE),
    "Public Authority": ("public.authority@nativelife.com", UserType.PUBLIC),
    "Business Profile": ("business.profile@nativelife.com", UserType.PUBLIC),
    "Promoter": ("promoter@nativelife.com", UserType.PUBLIC),
    "Public User": ("public.user@nativelife.com", UserType.PUBLIC),
    "Delivery Team Member": ("delivery.team.member@nativelife.com", UserType.PRIVATE),
}

DEFAULT_SETTINGS = {
    "app_name": "Native Life",
    "app_logo_url": None,
    "app_favicon_url": None,
    "app_site_motto": "Live Native. Live Free.",
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

        seeded_permissions = [
            _get_or_create_permission(permissions, name) for name in PERMISSION_NAMES
        ]

        for name in ROLE_USERS:
            slug = slugify(name)
            if roles.get_by_slug(slug) is None:
                roles.add(Role(name=name, slug=slug, permissions=[]))
                print(f"Seeded role: {name}")

        full_role = roles.get_by_slug(FULL_PERMISSIONS_ROLE_SLUG)
        if full_role is not None:
            full_role.permissions = seeded_permissions
            roles.save(full_role)
            print(
                f"Assigned {len(seeded_permissions)} permissions to role: "
                f"{full_role.name}"
            )
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
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles_and_permissions()
    seed_role_users()
    seed_settings()
