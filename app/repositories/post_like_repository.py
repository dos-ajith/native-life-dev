from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.post_like import PostLike, ReactionType


class PostLikeRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_post_and_user(self, post_id: UUID, user_id: UUID) -> PostLike | None:
        return self._db.scalar(
            select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user_id)
        )

    def count_by_type(self, post_ids: Sequence[UUID]) -> dict[UUID, dict[ReactionType, int]]:
        rows = self._db.execute(
            select(PostLike.post_id, PostLike.reaction_type, func.count())
            .where(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id, PostLike.reaction_type)
        ).all()
        counts: dict[UUID, dict[ReactionType, int]] = {}
        for post_id, reaction_type, total in rows:
            counts.setdefault(post_id, {})[reaction_type] = total
        return counts

    def list_user_reactions(
        self, user_id: UUID, post_ids: Sequence[UUID]
    ) -> dict[UUID, ReactionType]:
        rows = self._db.execute(
            select(PostLike.post_id, PostLike.reaction_type).where(
                PostLike.user_id == user_id, PostLike.post_id.in_(post_ids)
            )
        ).all()
        return {post_id: reaction_type for post_id, reaction_type in rows}

    def add(self, like: PostLike) -> PostLike:
        self._db.add(like)
        self._db.commit()
        self._db.refresh(like)
        return like

    def save(self, like: PostLike) -> PostLike:
        self._db.commit()
        self._db.refresh(like)
        return like

    def delete(self, like: PostLike) -> None:
        self._db.delete(like)
        self._db.commit()
