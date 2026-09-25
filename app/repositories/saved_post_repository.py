from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.saved_post import SavedPost


class SavedPostRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, user_id: UUID, post_id: UUID) -> bool:
        created_id = self._db.scalar(
            insert(SavedPost)
            .values(user_id=user_id, post_id=post_id)
            .on_conflict_do_nothing(constraint="uq_saved_posts_user_id_post_id")
            .returning(SavedPost.id)
        )
        self._db.commit()
        return created_id is not None

    def delete(self, user_id: UUID, post_id: UUID) -> bool:
        deleted_id = self._db.scalar(
            delete(SavedPost)
            .where(SavedPost.user_id == user_id, SavedPost.post_id == post_id)
            .returning(SavedPost.id)
        )
        self._db.commit()
        return deleted_id is not None

    def get_by_user_and_post(self, user_id: UUID, post_id: UUID) -> SavedPost | None:
        return self._db.scalar(
            select(SavedPost).where(SavedPost.user_id == user_id, SavedPost.post_id == post_id)
        )

    def exists(self, user_id: UUID, post_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    select(SavedPost.id)
                    .where(SavedPost.user_id == user_id, SavedPost.post_id == post_id)
                    .exists()
                )
            )
        )

    def list_saved_post_ids(self, user_id: UUID, post_ids: list[UUID]) -> set[UUID]:
        if not post_ids:
            return set()
        rows = self._db.scalars(
            select(SavedPost.post_id).where(
                SavedPost.user_id == user_id, SavedPost.post_id.in_(post_ids)
            )
        ).all()
        return set(rows)
