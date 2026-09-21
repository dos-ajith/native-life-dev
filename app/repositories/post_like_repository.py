from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post_like import PostLike


class PostLikeRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_post_and_user(self, post_id: UUID, user_id: UUID) -> PostLike | None:
        return self._db.scalar(
            select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user_id)
        )

    def add(self, like: PostLike) -> PostLike:
        self._db.add(like)
        self._db.commit()
        self._db.refresh(like)
        return like

    def delete(self, like: PostLike) -> None:
        self._db.delete(like)
        self._db.commit()
