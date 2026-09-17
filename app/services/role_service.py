from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.role import Role
from app.repositories.permission_repository import PermissionRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.pagination import PaginationParams
from app.schemas.role import RoleCreate, RoleUpdate


class RoleService:
    def __init__(self, db: Session) -> None:
        self._roles = RoleRepository(db)
        self._permissions = PermissionRepository(db)

    def create(self, payload: RoleCreate) -> Role:
        if self._roles.get_by_name(payload.name) is not None:
            raise BusinessRuleError("Role name is already in use")
        role = Role(name=payload.name, description=payload.description, permissions=[])
        return self._roles.add(role)

    def get(self, role_id: UUID) -> Role:
        role = self._roles.get_by_id(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        return role

    def update(self, role_id: UUID, payload: RoleUpdate) -> Role:
        role = self.get(role_id)
        data: dict[str, Any] = payload.model_dump(exclude_none=True)
        name = data.get("name")
        if name is not None and name != role.name and self._roles.get_by_name(name):
            raise BusinessRuleError("Role name is already in use")
        for field, value in data.items():
            setattr(role, field, value)
        return self._roles.save(role)

    def delete(self, role_id: UUID) -> None:
        role = self.get(role_id)
        self._roles.delete(role)

    def set_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> Role:
        role = self.get(role_id)
        permissions = self._permissions.get_by_ids(permission_ids)
        missing_ids = set(permission_ids) - {permission.id for permission in permissions}
        if missing_ids:
            names = ", ".join(str(permission_id) for permission_id in missing_ids)
            raise BusinessRuleError(f"Unknown permission id(s): {names}")
        role.permissions = permissions
        return self._roles.save(role)

    def list(self, params: PaginationParams) -> tuple[list[Role], int]:
        return self._roles.list(params)
