from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload

from app.models.user_has_role import UserRoleAssignment


class UserRoleAssignmentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_users(self, user_ids: Sequence[UUID]) -> list[UserRoleAssignment]:
        if not user_ids:
            return []
        return list(
            self._db.scalars(
                select(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(user_ids))
            )
        )

    def get_for_update(self, user_id: UUID, role_id: UUID) -> UserRoleAssignment | None:
        return self._db.scalar(
            select(UserRoleAssignment)
            .options(lazyload(UserRoleAssignment.role))
            .where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.role_id == role_id)
            .with_for_update(of=UserRoleAssignment)
        )
