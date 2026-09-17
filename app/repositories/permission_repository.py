from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.schemas.pagination import PaginationParams


class PermissionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, permission_id: UUID) -> Permission | None:
        return self._db.get(Permission, permission_id)

    def get_by_name(self, name: str) -> Permission | None:
        return self._db.scalar(select(Permission).where(Permission.name == name))

    def get_by_ids(self, permission_ids: list[UUID]) -> list[Permission]:
        return list(self._db.scalars(select(Permission).where(Permission.id.in_(permission_ids))))

    def list(self, params: PaginationParams) -> tuple[list[Permission], int]:
        total = self._db.scalar(select(func.count()).select_from(Permission)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Permission)
            .order_by(Permission.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, permission: Permission) -> Permission:
        self._db.add(permission)
        self._db.commit()
        self._db.refresh(permission)
        return permission

    def save(self, permission: Permission) -> Permission:
        self._db.commit()
        self._db.refresh(permission)
        return permission

    def delete(self, permission: Permission) -> None:
        self._db.delete(permission)
        self._db.commit()
