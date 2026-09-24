from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_follow_request import UserFollowRequest
from app.schemas.pagination import PaginationParams


class UserFollowRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, requester_id: UUID, target_id: UUID) -> bool:
        created_id = self._db.scalar(
            insert(UserFollowRequest)
            .values(requester_id=requester_id, target_id=target_id)
            .on_conflict_do_nothing(
                constraint="uq_user_follow_requests_requester_id_target_id"
            )
            .returning(UserFollowRequest.id)
        )
        self._db.commit()
        return created_id is not None

    def delete(self, requester_id: UUID, target_id: UUID) -> bool:
        deleted_id = self._db.scalar(
            delete(UserFollowRequest)
            .where(
                UserFollowRequest.requester_id == requester_id,
                UserFollowRequest.target_id == target_id,
            )
            .returning(UserFollowRequest.id)
        )
        self._db.commit()
        return deleted_id is not None

    def delete_all_for_target(self, target_id: UUID) -> list[UUID]:
        requester_ids = self._db.scalars(
            delete(UserFollowRequest)
            .where(UserFollowRequest.target_id == target_id)
            .returning(UserFollowRequest.requester_id)
        ).all()
        self._db.commit()
        return list(requester_ids)

    def exists(self, requester_id: UUID, target_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    select(UserFollowRequest.id)
                    .where(
                        UserFollowRequest.requester_id == requester_id,
                        UserFollowRequest.target_id == target_id,
                    )
                    .exists()
                )
            )
        )

    def count_incoming(self, target_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(UserFollowRequest)
                .join(User, User.id == UserFollowRequest.requester_id)
                .where(UserFollowRequest.target_id == target_id, User.deleted_at.is_(None))
            )
            or 0
        )

    def list_incoming(self, target_id: UUID, params: PaginationParams) -> list[User]:
        offset = (params.page - 1) * params.page_size
        return list(
            self._db.scalars(
                select(User)
                .join(UserFollowRequest, User.id == UserFollowRequest.requester_id)
                .where(UserFollowRequest.target_id == target_id, User.deleted_at.is_(None))
                .order_by(UserFollowRequest.created_at.desc(), UserFollowRequest.id.desc())
                .offset(offset)
                .limit(params.page_size)
            )
        )
