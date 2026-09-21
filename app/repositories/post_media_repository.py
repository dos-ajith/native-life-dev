from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post_media import PostMedia


class PostMediaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, media_id: UUID) -> PostMedia | None:
        return self._db.get(PostMedia, media_id)

    def list_by_post(self, post_id: UUID) -> list[PostMedia]:
        return list(
            self._db.scalars(
                select(PostMedia)
                .where(PostMedia.post_id == post_id)
                .order_by(PostMedia.sort_order, PostMedia.created_at)
            )
        )

    def list_by_posts(self, post_ids: list[UUID]) -> list[PostMedia]:
        if not post_ids:
            return []
        return list(
            self._db.scalars(
                select(PostMedia)
                .where(PostMedia.post_id.in_(post_ids))
                .order_by(PostMedia.post_id, PostMedia.sort_order, PostMedia.created_at)
            )
        )

    def add(self, media: PostMedia) -> PostMedia:
        self._db.add(media)
        self._db.commit()
        self._db.refresh(media)
        return media

    def delete(self, media: PostMedia) -> None:
        self._db.delete(media)
        self._db.commit()
