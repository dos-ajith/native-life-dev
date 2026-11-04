from collections.abc import Iterable

from app.core.permissions import GUEST_PERMISSIONS, RoleSlug
from app.models.role import Role
from app.models.user import User


def _role_grants(role: Role, permission: str) -> bool:
    return role.slug == RoleSlug.SUPER_ADMIN or any(
        granted.name == permission for granted in role.permissions
    )


def has_permission(user: User, permission: str) -> bool:
    return any(_role_grants(role, permission) for role in user.approved_roles)


def has_any_permission(user: User, permissions: Iterable[str]) -> bool:
    return any(has_permission(user, permission) for permission in permissions)


def is_super_admin(user: User) -> bool:
    return any(role.slug == RoleSlug.SUPER_ADMIN for role in user.approved_roles)


def guest_has_permission(permission: str) -> bool:
    return permission in GUEST_PERMISSIONS
