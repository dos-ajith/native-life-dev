from sqlalchemy.orm import Session

from app.core.permissions import RoleSlug
from app.models.role import Role
from app.models.user import User
from app.repositories.role_repository import RoleRepository


def _role_grants(role: Role, permission: str) -> bool:
    return role.slug == RoleSlug.SUPER_ADMIN or any(
        granted.name == permission for granted in role.permissions
    )


def has_permission(user: User, permission: str) -> bool:
    return any(_role_grants(role, permission) for role in user.roles)


def guest_has_permission(db: Session, permission: str) -> bool:
    guest_role = RoleRepository(db).get_by_slug(RoleSlug.GUEST)
    return guest_role is not None and _role_grants(guest_role, permission)
