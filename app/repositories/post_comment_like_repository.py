from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post_comment_like import PostCommentLike


class PostCommentLikeRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_comment_and_user(self, comment_id: UUID, user_id: UUID) -> PostCommentLike | None:
        return self._db.scalar(
            select(PostCommentLike).where(
                PostCommentLike.comment_id == comment_id, PostCommentLike.user_id == user_id
            )
        )

    def list_liked_comment_ids(self, user_id: UUID, comment_ids: Sequence[UUID]) -> set[UUID]:
        if not comment_ids:
            return set()
        return set(
            self._db.scalars(
                select(PostCommentLike.comment_id).where(
                    PostCommentLike.user_id == user_id,
                    PostCommentLike.comment_id.in_(comment_ids),
                )
            )
        )

    def add(self, like: PostCommentLike) -> PostCommentLike:
        self._db.add(like)
        self._db.commit()
        self._db.refresh(like)
        return like

    def delete(self, like: PostCommentLike) -> None:
        self._db.delete(like)
        self._db.commit()
