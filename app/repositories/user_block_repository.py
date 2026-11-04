from collections.abc import Collection
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_block import UserBlock
from app.schemas.pagination import PaginationParams


class UserBlockRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, blocker_id: UUID, blocked_id: UUID) -> bool:
        created_id = self._db.scalar(
            insert(UserBlock)
            .values(blocker_id=blocker_id, blocked_id=blocked_id)
            .on_conflict_do_nothing(constraint="uq_user_blocks_blocker_id_blocked_id")
            .returning(UserBlock.id)
        )
        self._db.commit()
        return created_id is not None

    def delete(self, blocker_id: UUID, blocked_id: UUID) -> bool:
        deleted_id = self._db.scalar(
            delete(UserBlock)
            .where(UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id)
            .returning(UserBlock.id)
        )
        self._db.commit()
        return deleted_id is not None

    def exists_between(self, first_id: UUID, second_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    select(UserBlock.id)
                    .where(
                        or_(
                            and_(
                                UserBlock.blocker_id == first_id, UserBlock.blocked_id == second_id
                            ),
                            and_(
                                UserBlock.blocker_id == second_id, UserBlock.blocked_id == first_id
                            ),
                        )
                    )
                    .exists()
                )
            )
        )

    def blocked_among(self, blocker_id: UUID, user_ids: Collection[UUID]) -> set[UUID]:
        if not user_ids:
            return set()
        return set(
            self._db.scalars(
                select(UserBlock.blocked_id).where(
                    UserBlock.blocker_id == blocker_id, UserBlock.blocked_id.in_(user_ids)
                )
            )
        )

    def list_blocked(self, blocker_id: UUID, params: PaginationParams) -> tuple[list[User], int]:
        condition = and_(UserBlock.blocker_id == blocker_id, User.deleted_at.is_(None))
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(UserBlock)
                .join(User, User.id == UserBlock.blocked_id)
                .where(condition)
            )
            or 0
        )
        offset = (params.page - 1) * params.page_size
        users = self._db.scalars(
            select(User)
            .join(UserBlock, User.id == UserBlock.blocked_id)
            .where(condition)
            .order_by(UserBlock.created_at.desc(), UserBlock.id.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        return list(users), total
