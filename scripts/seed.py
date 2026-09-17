from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from app.repositories.permission_repository import PermissionRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository

DEV_USER_EMAIL = "dev@nativelife.example"
DEV_USER_PASSWORD = "Password123!"

ROLE_NAMES = ("admin", "customer", "promoter")
PERMISSION_NAMES = ("user.view", "user.create", "user.update", "user.delete")
ADMIN_ROLE_NAME = "admin"


def seed_dev_user() -> None:
    db = SessionLocal()
    try:
        repository = UserRepository(db)
        if repository.get_by_email(DEV_USER_EMAIL) is not None:
            print(f"Dev user already exists: {DEV_USER_EMAIL}")
            return
        user = User(
            first_name="Dev",
            last_name="User",
            email=DEV_USER_EMAIL,
            password_hash=hash_password(DEV_USER_PASSWORD),
            status=UserStatus.ACTIVE,
            user_type=UserType.PRIVATE,
        )
        db.add(user)
        db.commit()
        print(f"Seeded dev user: {DEV_USER_EMAIL} / {DEV_USER_PASSWORD}")
    finally:
        db.close()


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


if __name__ == "__main__":
    seed_dev_user()
    seed_roles_and_permissions()
