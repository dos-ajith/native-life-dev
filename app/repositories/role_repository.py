from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.schemas.pagination import PaginationParams


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, role_id: UUID) -> Role | None:
        return self._db.get(Role, role_id)

    def get_by_name(self, name: str) -> Role | None:
        return self._db.scalar(select(Role).where(Role.name == name))

    def get_by_ids(self, role_ids: list[UUID]) -> list[Role]:
        return list(self._db.scalars(select(Role).where(Role.id.in_(role_ids))))

    def list(self, params: PaginationParams) -> tuple[list[Role], int]:
        total = self._db.scalar(select(func.count()).select_from(Role)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Role).order_by(Role.created_at.desc()).offset(offset).limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, role: Role) -> Role:
        self._db.add(role)
        self._db.commit()
        self._db.refresh(role)
        return role

    def save(self, role: Role) -> Role:
        self._db.commit()
        self._db.refresh(role)
        return role

    def delete(self, role: Role) -> None:
        self._db.delete(role)
        self._db.commit()
