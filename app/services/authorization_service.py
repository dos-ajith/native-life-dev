from app.core.permissions import GUEST_PERMISSIONS, RoleSlug
from app.models.role import Role
from app.models.user import User


def _role_grants(role: Role, permission: str) -> bool:
    return role.slug == RoleSlug.SUPER_ADMIN or any(
        granted.name == permission for granted in role.permissions
    )


def has_permission(user: User, permission: str) -> bool:
    return any(_role_grants(role, permission) for role in user.roles)


def guest_has_permission(permission: str) -> bool:
    return permission in GUEST_PERMISSIONS
