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

ADMIN_USER_EMAIL = "dev@nativelife.example"
ADMIN_USER_PASSWORD = "Password123!"

ROLE_NAMES = ("admin", "customer", "promoter")
PERMISSION_NAMES = ("user.view", "user.create", "user.update", "user.delete")
ADMIN_ROLE_NAME = "admin"

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

        for name in ROLE_NAMES:
            if roles.get_by_name(name) is None:
                roles.add(Role(name=name, permissions=[]))
                print(f"Seeded role: {name}")

        admin_role = roles.get_by_name(ADMIN_ROLE_NAME)
        if admin_role is not None:
            admin_role.permissions = seeded_permissions
            roles.save(admin_role)
            print(f"Assigned {len(seeded_permissions)} permissions to role: {ADMIN_ROLE_NAME}")
    finally:
        db.close()


def seed_admin_user() -> None:
    db = SessionLocal()
    try:
        users = UserRepository(db)
        roles = RoleRepository(db)

        admin_role = roles.get_by_name(ADMIN_ROLE_NAME)
        if admin_role is None:
            raise RuntimeError(
                f"Role '{ADMIN_ROLE_NAME}' does not exist. Run seed_roles_and_permissions first."
            )

        user = users.get_by_email(ADMIN_USER_EMAIL)
        if user is None:
            user = User(
                first_name="Dev",
                last_name="Admin",
                email=ADMIN_USER_EMAIL,
                password_hash=hash_password(ADMIN_USER_PASSWORD),
                status=UserStatus.ACTIVE,
                user_type=UserType.PRIVATE,
                roles=[admin_role],
            )
            users.add(user)
            print(f"Seeded admin user: {ADMIN_USER_EMAIL} / {ADMIN_USER_PASSWORD}")
            return

        if admin_role not in user.roles:
            user.roles.append(admin_role)
            users.save(user)
            print(f"Assigned role '{ADMIN_ROLE_NAME}' to existing user: {ADMIN_USER_EMAIL}")
        else:
            print(f"Admin user already has role '{ADMIN_ROLE_NAME}': {ADMIN_USER_EMAIL}")
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
    seed_admin_user()
    seed_settings()
