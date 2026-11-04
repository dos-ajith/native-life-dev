from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.permissions import CANONICAL_ROLE_SLUGS
from app.models.role import Role
from app.models.user_has_role import user_has_roles
from app.schemas.pagination import PaginationParams


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, role_id: UUID) -> Role | None:
        return self._db.get(Role, role_id)

    def get_by_name(self, name: str) -> Role | None:
        return self._db.scalar(select(Role).where(Role.name == name))

    def get_by_slug(self, slug: str) -> Role | None:
        return self._db.scalar(select(Role).where(Role.slug == slug))

    def get_by_ids(self, role_ids: list[UUID]) -> list[Role]:
        return list(self._db.scalars(select(Role).where(Role.id.in_(role_ids))))

    def list_by_slugs(self, slugs: Sequence[str]) -> list[Role]:
        found = self._db.scalars(select(Role).where(Role.slug.in_(slugs)))
        roles = {role.slug: role for role in found}
        return [roles[slug] for slug in slugs if slug in roles]

    def list_all(self) -> list[Role]:
        return list(self._db.scalars(select(Role)))

    def count_holders(self, role_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(user_has_roles)
                .where(user_has_roles.c.role_id == role_id)
            )
            or 0
        )

    def list(self, params: PaginationParams) -> tuple[list[Role], int]:
        total = self._db.scalar(select(func.count()).select_from(Role)) or 0
        offset = (params.page - 1) * params.page_size
        canonical_position = case(
            {slug: position for position, slug in enumerate(CANONICAL_ROLE_SLUGS)},
            value=Role.slug,
            else_=len(CANONICAL_ROLE_SLUGS),
        )
        items = self._db.scalars(
            select(Role)
            .order_by(canonical_position, Role.name)
            .offset(offset)
            .limit(params.page_size)
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
