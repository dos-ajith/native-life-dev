from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import PermissionMessages
from app.models.permission import Permission
from app.repositories.permission_repository import PermissionRepository
from app.schemas.pagination import PaginationParams
from app.schemas.permission import PermissionCreate, PermissionUpdate


class PermissionService:
    def __init__(self, db: Session) -> None:
        self._permissions = PermissionRepository(db)

    def create(self, payload: PermissionCreate) -> Permission:
        if self._permissions.get_by_name(payload.name) is not None:
            raise BusinessRuleError(PermissionMessages.NAME_TAKEN)
        permission = Permission(name=payload.name, description=payload.description)
        return self._permissions.add(permission)

    def get(self, permission_id: UUID) -> Permission:
        permission = self._permissions.get_by_id(permission_id)
        if permission is None:
            raise NotFoundError(PermissionMessages.NOT_FOUND)
        return permission

    def list(self, params: PaginationParams) -> tuple[list[Permission], int]:
        return self._permissions.list(params)

    def update(self, permission_id: UUID, payload: PermissionUpdate) -> Permission:
        permission = self.get(permission_id)
        data: dict[str, Any] = payload.model_dump(exclude_none=True)
        self._check_uniqueness(permission, data)
        for field, value in data.items():
            setattr(permission, field, value)
        return self._permissions.save(permission)

    def delete(self, permission_id: UUID) -> None:
        permission = self.get(permission_id)
        self._permissions.delete(permission)

    def _check_uniqueness(self, permission: Permission, data: dict[str, Any]) -> None:
        name = data.get("name")
        if name is not None and name != permission.name and self._permissions.get_by_name(name):
            raise BusinessRuleError(PermissionMessages.NAME_TAKEN)
