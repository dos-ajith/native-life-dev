from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.collection_post import CollectionPost


class CollectionPostRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, collection_id: UUID, saved_post_id: UUID) -> bool:
        created_id = self._db.scalar(
            insert(CollectionPost)
            .values(collection_id=collection_id, saved_post_id=saved_post_id)
            .on_conflict_do_nothing(
                constraint="uq_collection_posts_collection_id_saved_post_id"
            )
            .returning(CollectionPost.id)
        )
        self._db.commit()
        return created_id is not None

    def delete(self, collection_id: UUID, saved_post_id: UUID) -> bool:
        deleted_id = self._db.scalar(
            delete(CollectionPost)
            .where(
                CollectionPost.collection_id == collection_id,
                CollectionPost.saved_post_id == saved_post_id,
            )
            .returning(CollectionPost.id)
        )
        self._db.commit()
        return deleted_id is not None

    def count_by_collection(self, collection_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(CollectionPost)
                .where(CollectionPost.collection_id == collection_id)
            )
            or 0
        )

    def count_by_collections(self, collection_ids: list[UUID]) -> dict[UUID, int]:
        if not collection_ids:
            return {}
        rows = self._db.execute(
            select(CollectionPost.collection_id, func.count())
            .where(CollectionPost.collection_id.in_(collection_ids))
            .group_by(CollectionPost.collection_id)
        ).all()
        return {collection_id: count for collection_id, count in rows}
