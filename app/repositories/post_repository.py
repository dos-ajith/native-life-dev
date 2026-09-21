from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.post import Post
from app.schemas.pagination import PaginationParams


class PostRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, post_id: UUID) -> Post | None:
        return self._db.scalar(
            select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
        )

    def list(self, params: PaginationParams) -> tuple[list[Post], int]:
        not_deleted = Post.deleted_at.is_(None)
        total = self._db.scalar(select(func.count()).select_from(Post).where(not_deleted)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Post)
            .where(not_deleted)
            .order_by(Post.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, post: Post) -> Post:
        self._db.add(post)
        self._db.commit()
        self._db.refresh(post)
        return post

    def save(self, post: Post) -> Post:
        self._db.commit()
        self._db.refresh(post)
        return post

    def soft_delete(self, post: Post) -> None:
        post.deleted_at = datetime.now(UTC)
        self._db.commit()

    def increment_likes(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.likes_count, 1)

    def decrement_likes(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.likes_count, -1)

    def increment_comments(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.comments_count, 1)

    def decrement_comments(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.comments_count, -1)

    def increment_shares(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.shares_count, 1)

    def _adjust_count(
        self, post_id: UUID, column: InstrumentedAttribute[int], delta: int
    ) -> None:
        self._db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values({column: func.greatest(column + delta, 0)})
        )
        self._db.commit()
