from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
        total = (
            self._db.scalar(select(func.count()).select_from(PostComment).where(root_only)) or 0
        )
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
        comment.deleted_at = datetime.now(UTC)
        self._db.commit()
