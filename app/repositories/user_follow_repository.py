from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.user import User
from app.models.user_follow import UserFollow
from app.schemas.pagination import PaginationParams


class UserFollowRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, follower_id: UUID, following_id: UUID) -> bool:
        created_id = self._db.scalar(
            insert(UserFollow)
            .values(follower_id=follower_id, following_id=following_id)
            .on_conflict_do_nothing(constraint="uq_user_follows_follower_id_following_id")
            .returning(UserFollow.id)
        )
        self._db.commit()
        return created_id is not None

    def delete(self, follower_id: UUID, following_id: UUID) -> bool:
        deleted_id = self._db.scalar(
            delete(UserFollow)
            .where(UserFollow.follower_id == follower_id, UserFollow.following_id == following_id)
            .returning(UserFollow.id)
        )
        self._db.commit()
        return deleted_id is not None

    def exists(self, follower_id: UUID, following_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    select(UserFollow.id)
                    .where(
                        UserFollow.follower_id == follower_id,
                        UserFollow.following_id == following_id,
                    )
                    .exists()
                )
            )
        )

    def count_followers(self, user_id: UUID) -> int:
        return self._count(UserFollow.follower_id, UserFollow.following_id == user_id)

    def count_following(self, user_id: UUID) -> int:
        return self._count(UserFollow.following_id, UserFollow.follower_id == user_id)

    def list_followers(self, user_id: UUID, params: PaginationParams) -> list[User]:
        return self._list(UserFollow.follower_id, UserFollow.following_id == user_id, params)

    def list_following(self, user_id: UUID, params: PaginationParams) -> list[User]:
        return self._list(UserFollow.following_id, UserFollow.follower_id == user_id, params)

    def _count(
        self, other_user_column: InstrumentedAttribute[UUID], condition: ColumnElement[bool]
    ) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(UserFollow)
                .join(User, User.id == other_user_column)
                .where(condition, User.deleted_at.is_(None))
            )
            or 0
        )

    def _list(
        self,
        other_user_column: InstrumentedAttribute[UUID],
        condition: ColumnElement[bool],
        params: PaginationParams,
    ) -> list[User]:
        offset = (params.page - 1) * params.page_size
        return list(
            self._db.scalars(
                select(User)
                .join(UserFollow, User.id == other_user_column)
                .where(condition, User.deleted_at.is_(None))
                .order_by(UserFollow.created_at.desc(), UserFollow.id.desc())
                .offset(offset)
                .limit(params.page_size)
            )
        )
