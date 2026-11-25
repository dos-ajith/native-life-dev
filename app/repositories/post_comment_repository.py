from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.timezone import app_now
from app.models.post_comment import PostComment
from app.schemas.pagination import PaginationParams


class PostCommentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, comment_id: UUID) -> PostComment | None:
        return self._db.scalar(
            select(PostComment).where(
                PostComment.id == comment_id, PostComment.deleted_at.is_(None)
            )
        )

    def list_roots_by_post(
        self, post_id: UUID, params: PaginationParams
    ) -> tuple[list[PostComment], int]:
        root_only = (
            (PostComment.post_id == post_id)
            & PostComment.deleted_at.is_(None)
            & PostComment.parent_id.is_(None)
        )
        total = self._db.scalar(select(func.count()).select_from(PostComment).where(root_only)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(PostComment)
            .where(root_only)
            .order_by(PostComment.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_all_by_post(self, post_id: UUID) -> list[PostComment]:
        return list(
            self._db.scalars(
                select(PostComment)
                .where(PostComment.post_id == post_id, PostComment.deleted_at.is_(None))
                .order_by(PostComment.created_at)
            )
        )

    def add(self, comment: PostComment) -> PostComment:
        self._db.add(comment)
        self._db.commit()
        self._db.refresh(comment)
        return comment

    def soft_delete(self, comment: PostComment) -> None:
        comment.deleted_at = app_now()
        self._db.commit()

    def increment_likes(self, comment_id: UUID) -> None:
        self._adjust_likes(comment_id, 1)

    def decrement_likes(self, comment_id: UUID) -> None:
        self._adjust_likes(comment_id, -1)

    def _adjust_likes(self, comment_id: UUID, delta: int) -> None:
        self._db.execute(
            update(PostComment)
            .where(PostComment.id == comment_id)
            .values(likes_count=func.greatest(PostComment.likes_count + delta, 0))
        )
        self._db.commit()
